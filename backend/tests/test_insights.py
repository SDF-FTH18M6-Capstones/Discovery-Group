from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.extensions import db
from app.insights import accuracy, predict, weekday_factors
from app.models import (
    Category,
    Expense,
    MoneyImport,
    MoneyTransaction,
    Product,
    Sale,
    SaleItem,
)

NAIROBI = ZoneInfo("Africa/Nairobi")
WEEK = [100, 100, 100, 100, 200, 300, 50]


def today():
    return datetime.now(NAIROBI).date()


def at(day, hour=12):
    return datetime.combine(day, time(hour), NAIROBI).astimezone(UTC)


@pytest.fixture()
def tea():
    category = Category(name="Drinks")
    db.session.add(category)
    db.session.flush()
    product = Product(
        sku="TEA",
        name="Tea",
        category_id=category.id,
        cost_price=Decimal("20"),
        selling_price=Decimal("50"),
        quantity=12,
        reorder_level=2,
        created_at=datetime.now(UTC) - timedelta(days=90),
    )
    db.session.add(product)
    db.session.commit()
    return product


def ring(attendant_id, product, day, quantity=2, total=None):
    sale = Sale(
        attendant_id=attendant_id,
        payment_method="cash",
        total=total if total is not None else product.selling_price * quantity,
        created_at=at(day),
    )
    sale.items.append(
        SaleItem(
            product_id=product.id,
            quantity=quantity,
            unit_price=product.selling_price,
            unit_cost=product.cost_price,
        )
    )
    db.session.add(sale)


def weeks_of_sales(attendant_id, product, weeks=6):
    for back in range(1, weeks * 7 + 1):
        day = today() - timedelta(days=back)
        ring(attendant_id, product, day, quantity=1, total=Decimal(WEEK[day.weekday()]))
    db.session.commit()


def test_weekday_patterns_are_learned():
    start = date(2026, 1, 5)
    history = [(start + timedelta(days=n), float(WEEK[n % 7])) for n in range(56)]

    factors = weekday_factors(history[-56:])
    guesses = predict(history, start + timedelta(days=56), 7)

    assert factors[5] > factors[0] > factors[6]
    for guess in guesses:
        actual = WEEK[guess["date"].weekday()]
        assert abs(guess["expected"] - actual) <= 0.15 * actual
    assert all(g["low"] <= g["expected"] <= g["high"] for g in guesses)
    assert accuracy(history) >= 90


def test_accuracy_needs_enough_history():
    history = [(date(2026, 1, 1) + timedelta(days=n), 10.0) for n in range(20)]

    assert accuracy(history) is None


def test_too_little_history_says_so(admin, tea):
    ring(admin.user.id, tea, today() - timedelta(days=3))
    db.session.commit()

    sales = admin.get("/api/insights").json["sales"]

    assert (sales["ready"], sales["days_of_history"], sales["forecast"]) == (False, 3, [])


def test_a_forecast_with_a_range_and_accuracy(admin, tea):
    weeks_of_sales(admin.user.id, tea)

    sales = admin.get("/api/insights").json["sales"]

    assert sales["ready"] is True
    assert len(sales["forecast"]) == 14
    assert sales["forecast"][0]["date"] == today().isoformat()
    saturday = next(p for p in sales["forecast"] if date.fromisoformat(p["date"]).weekday() == 5)
    sunday = next(p for p in sales["forecast"] if date.fromisoformat(p["date"]).weekday() == 6)
    assert saturday["expected"] > sunday["expected"]
    assert sales["accuracy"] >= 90
    assert len(sales["history"]) == 42


def test_takings_from_the_statement_count_without_a_till(admin):
    batch = MoneyImport(source="sms", added=0, duplicates=0, skipped=0, created_by=admin.user.id)
    db.session.add(batch)
    for back in range(1, 22):
        day = today() - timedelta(days=back)
        batch.transactions.append(
            MoneyTransaction(
                receipt=f"SMS{back:07d}",
                occurred_at=at(day),
                direction="in",
                amount=Decimal(WEEK[day.weekday()]),
                kind="received",
                category="sales",
                counterparty="MARY" if back % 7 else "JOHN",
            )
        )
    db.session.commit()

    insights = admin.get("/api/insights").json

    assert insights["sales"]["ready"] is True
    assert insights["customers"]["top"][0]["name"] == "MARY"


def test_comparisons_with_a_usual_day(admin, tea):
    weeks_of_sales(admin.user.id, tea)

    notes = {note["key"]: note for note in admin.get("/api/insights").json["sales"]["comparisons"]}

    yesterday = today() - timedelta(days=1)
    assert notes["yesterday"]["value"] == WEEK[yesterday.weekday()]
    assert notes["yesterday"]["change"] == 0
    assert "week" in notes or today().weekday() == 0


def test_stock_that_will_run_out_and_stock_that_sits(admin, tea):
    for back in range(1, 30):
        ring(admin.user.id, tea, today() - timedelta(days=back), quantity=2)
    still = Product(
        sku="OLD",
        name="Umbrella",
        category_id=tea.category_id,
        cost_price=Decimal("300"),
        selling_price=Decimal("500"),
        quantity=4,
        created_at=datetime.now(UTC) - timedelta(days=60),
    )
    db.session.add(still)
    db.session.commit()

    stock = admin.get("/api/insights").json["stock"]

    assert stock["running_out"] == [
        {
            "id": tea.id,
            "name": "Tea",
            "quantity": 12,
            "per_day": 1.9,
            "days_left": 6,
            "suggested_order": 16,
        }
    ]
    assert stock["slow_movers"] == [
        {"id": still.id, "name": "Umbrella", "quantity": 4, "tied_up": 1200.0}
    ]
    assert stock["most_profitable"][0] == {
        "id": tea.id,
        "name": "Tea",
        "profit": 1740.0,
        "sold": 58,
    }


def regular(batch, name, days):
    for back in days:
        batch.transactions.append(
            MoneyTransaction(
                receipt=f"{name[:3].upper()}{back:07d}",
                occurred_at=at(today() - timedelta(days=back)),
                direction="in",
                amount=Decimal("100"),
                kind="received",
                category="sales",
                counterparty=name,
            )
        )


def test_customers_who_have_gone_quiet(admin):
    batch = MoneyImport(source="sms", added=0, duplicates=0, skipped=0, created_by=admin.user.id)
    db.session.add(batch)
    regular(batch, "ANN", [40, 45, 50, 55])
    regular(batch, "BEN", [1, 5, 9])
    db.session.commit()

    customers = admin.get("/api/insights").json["customers"]

    assert [c["name"] for c in customers["gone_quiet"]] == ["ANN"]
    assert [(c["name"], c["total"]) for c in customers["top"]] == [("ANN", 400.0), ("BEN", 300.0)]


def test_cashflow_projects_the_month_ahead(admin, tea):
    weeks_of_sales(admin.user.id, tea)
    batch = MoneyImport(source="sms", added=0, duplicates=0, skipped=0, created_by=admin.user.id)
    db.session.add(batch)
    batch.transactions.append(
        MoneyTransaction(
            receipt="RENT000001",
            occurred_at=at(today() - timedelta(days=10)),
            direction="out",
            amount=Decimal("3000"),
            balance=Decimal("5000"),
            kind="paybill",
            category="rent",
            counterparty="LANDLORD",
        )
    )
    batch.transactions.append(
        MoneyTransaction(
            receipt="CASH000001",
            occurred_at=at(today() - timedelta(days=9)),
            direction="out",
            amount=Decimal("1000"),
            kind="withdrawal",
            category="withdrawal",
            counterparty="AGENT",
        )
    )
    db.session.add(
        Expense(
            spent_on=today() - timedelta(days=5),
            category="Transport",
            amount=1000,
            created_by=admin.user.id,
        )
    )
    db.session.commit()

    cash = admin.get("/api/insights").json["cash"]

    assert cash["ready"] is True
    assert cash["expected_out"] == 2000.0
    assert cash["expected_in"] > 3000
    assert cash["expected_net"] == round(cash["expected_in"] - 2000.0, 2)
    assert cash["balance"] == 5000.0
    assert cash["projected_balance"] == round(5000.0 + cash["expected_net"], 2)
    assert len(cash["weeks"]) == 8
    assert sum(week["out"] for week in cash["weeks"]) == 4000.0


def test_insights_are_for_the_administrator(as_role):
    assert as_role("sales").get("/api/insights").status_code == 403
