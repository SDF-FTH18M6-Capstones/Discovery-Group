import io
from datetime import UTC, date, datetime
from decimal import Decimal

from pypdf import PdfReader

from app.extensions import db
from app.loanreport import figures, month_starts
from app.models import Business, Category, Expense, MoneyImport, MoneyTransaction, Product, Sale

TODAY = date(2026, 11, 28)


def at(day):
    return datetime(day.year, day.month, day.day, 9, tzinfo=UTC)


def money_row(batch, receipt, day, direction, amount, category, who="X", balance=None):
    batch.transactions.append(
        MoneyTransaction(
            receipt=receipt,
            occurred_at=at(day),
            direction=direction,
            amount=Decimal(amount),
            kind="other",
            category=category,
            counterparty=who,
            phone=None,
            balance=Decimal(balance) if balance else None,
        )
    )


def history(admin):
    category = Category(name="Grocery")
    db.session.add(category)
    db.session.flush()
    db.session.add(
        Product(
            sku="RICE",
            name="Rice",
            category_id=category.id,
            cost_price=Decimal("100"),
            selling_price=Decimal("150"),
            quantity=10,
        )
    )
    for day, total in ((date(2026, 9, 3), "1000"), (date(2026, 10, 5), "2000")):
        db.session.add(
            Sale(
                attendant_id=admin.user.id,
                payment_method="cash",
                total=Decimal(total),
                created_at=at(day),
            )
        )
    db.session.add(
        Sale(
            attendant_id=admin.user.id,
            payment_method="cash",
            total=Decimal("999"),
            status="voided",
            created_at=at(date(2026, 10, 6)),
        )
    )
    batch = MoneyImport(
        source="statement", added=0, duplicates=0, skipped=0, created_by=admin.user.id
    )
    money_row(batch, "A000000001", date(2026, 9, 10), "in", "500", "sales", "JANE", "5500")
    money_row(batch, "A000000002", date(2026, 10, 10), "in", "700", "sales", "JANE")
    money_row(batch, "A000000003", date(2026, 10, 11), "in", "300", "sales", "JANE", "6000")
    money_row(batch, "A000000004", date(2026, 10, 12), "in", "1000", "loan", "Fuliza M-Pesa")
    money_row(
        batch, "A000000005", date(2026, 10, 13), "out", "400", "loan_repayment", "Fuliza M-Pesa"
    )
    money_row(batch, "A000000006", date(2026, 10, 14), "out", "5000", "withdrawal", "AGENT")
    money_row(batch, "A000000007", date(2026, 10, 15), "out", "800", "stock", "METRO")
    money_row(batch, "A000000008", date(2026, 7, 15), "in", "9999", "sales", "TOO EARLY")
    db.session.add(batch)
    db.session.add(
        Expense(
            spent_on=date(2026, 10, 20),
            category="Rent",
            amount=Decimal("1500"),
            created_by=admin.user.id,
        )
    )
    db.session.commit()


def test_months_run_up_to_last_month():
    assert month_starts(TODAY, 3) == [date(2026, 8, 1), date(2026, 9, 1), date(2026, 10, 1)]
    assert month_starts(date(2026, 1, 15), 2) == [date(2025, 11, 1), date(2025, 12, 1)]


def test_the_figures_add_up(admin):
    history(admin)
    business = db.session.get(Business, admin.user.business_id)

    data = figures(business, 3, TODAY)

    rows = {row["month"].month: row for row in data["rows"]}
    assert rows[8]["sales"] == 0
    assert (rows[9]["sales"], rows[9]["balance"]) == (Decimal("1500"), Decimal("5500"))
    assert rows[10]["sales"] == Decimal("3000")
    assert rows[10]["other_in"] == Decimal("1000")
    assert rows[10]["spending"] == Decimal("2700")
    assert rows[10]["net"] == Decimal("1300")
    assert (data["borrowed"], data["repaid"]) == (Decimal("1000"), Decimal("400"))
    assert (data["customers"], data["regulars"]) == (1, 1)
    assert data["best"]["month"] == date(2026, 10, 1)
    assert data["positive_months"] == 2
    assert data["stock_value"] == Decimal("1000")
    assert data["mpesa_rows"] == 7
    assert data["growth"] is None
    assert figures(business, 6, TODAY)["growth"] == -55


def test_the_report_downloads_as_a_pdf(admin):
    history(admin)

    response = admin.get("/api/reports/performance.pdf?months=6")

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert "test-shop-performance-" in response.headers["Content-Disposition"]
    pages = PdfReader(io.BytesIO(response.data)).pages
    text = " ".join(" ".join(page.extract_text().split()) for page in pages)
    assert "Test Shop" in text
    assert "Business performance report" in text
    assert "Month by month" in text
    assert "have not been audited" in text


def test_only_these_periods_and_only_the_owner(admin, as_role):
    assert admin.get("/api/reports/performance.pdf?months=5").status_code == 422
    assert as_role("sales").get("/api/reports/performance.pdf").status_code == 403


def test_an_empty_business_still_gets_a_report(admin):
    response = admin.get("/api/reports/performance.pdf?months=3")

    assert response.status_code == 200
    assert response.data.startswith(b"%PDF")
