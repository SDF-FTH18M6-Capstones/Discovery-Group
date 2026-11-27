from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import (
    Business,
    Category,
    MoneyImport,
    MoneyTransaction,
    Product,
    Purchase,
    Supplier,
)
from tests.test_insights import at, ring, today

TOKEN = {"X-Task-Token": "test-task-token"}


@pytest.fixture()
def shelf():
    category = Category(name="Drinks")
    db.session.add(category)
    db.session.flush()
    products = [
        Product(
            sku=sku,
            name=name,
            category_id=category.id,
            cost_price=Decimal("10"),
            selling_price=Decimal(price),
            quantity=quantity,
            reorder_level=5,
        )
        for sku, name, price, quantity in [
            ("TEA", "Tea", "100", 20),
            ("COF", "Coffee", "150", 20),
            ("JUI", "Juice", "80", 3),
        ]
    ]
    db.session.add_all(products)
    db.session.commit()
    return {p.name: p.id for p in products}


def sell(client, product_id, quantity, method="cash"):
    return client.post(
        "/api/sales/",
        json={
            "payment_method": method,
            "items": [{"product_id": product_id, "quantity": quantity}],
        },
    ).json


def test_the_task_needs_its_token(client):
    assert client.post("/api/tasks/daily-summary").status_code == 404
    assert client.post("/api/tasks/daily-summary", headers={"X-Task-Token": "x"}).status_code == 404


def test_the_task_is_off_without_a_token(client, app):
    app.config["TASK_TOKEN"] = ""
    response = client.post("/api/tasks/daily-summary", headers={"X-Task-Token": ""})
    app.config["TASK_TOKEN"] = "test-task-token"

    assert response.status_code == 404


def test_admins_get_the_day_in_one_email(client, admin, as_role, shelf, outbox):
    seller = as_role("sales")
    sell(seller, shelf["Tea"], 3)
    sell(seller, shelf["Coffee"], 1, "mpesa")
    voided = sell(seller, shelf["Tea"], 1)
    seller.post(f"/api/sales/{voided['id']}/void", json={"reason": "Mistake"})
    supplier = Supplier(name="Metro")
    db.session.add(supplier)
    db.session.flush()
    db.session.add(Purchase(supplier_id=supplier.id, created_by=admin.user.id, total=0))
    db.session.commit()

    response = client.post("/api/tasks/daily-summary", headers=TOKEN)

    assert response.json == {"sent": 1}
    [email] = [mail for mail in outbox if mail["to"] == admin.user.email]
    assert email["subject"] == "Test Shop today: KES 450.00 from 2 sales"
    body = email["body"]
    assert "Sales: 2 receipts, KES 450.00" in body
    assert "  Cash: KES 300.00" in body
    assert "  M-Pesa: KES 150.00" in body
    assert "Best sellers: Tea (3), Coffee (1)" in body
    assert "Voided: 1 receipt" in body
    assert "Low on stock: Juice" in body
    assert "Draft orders waiting for Procurement to confirm: 1" in body


def test_a_quiet_day_still_reports(client, admin, outbox):
    client.post("/api/tasks/daily-summary", headers=TOKEN)

    body = outbox[-1]["body"]
    assert "No sales were recorded today." in body
    assert "Nothing is waiting on anyone." in body


def test_it_sends_once_a_day(client, admin, outbox):
    first = client.post("/api/tasks/daily-summary", headers=TOKEN).json
    second = client.post("/api/tasks/daily-summary", headers=TOKEN).json

    assert (first, second) == ({"sent": 1}, {"sent": 0})


def test_businesses_can_turn_it_off(client, admin, outbox):
    business = admin.get("/api/business").json
    keep = ("name", "timezone", "currency", "vat_rate", "phone", "email", "address")
    admin.put(
        "/api/business",
        json={**{k: business[k] for k in keep}, "receipt_footer": None, "daily_summary": False},
    )

    assert db.session.get(Business, business["id"]).daily_summary is False
    assert client.post("/api/tasks/daily-summary", headers=TOKEN).json == {"sent": 0}


def test_the_command_line_sends_it_too(app, admin, outbox):
    result = app.test_cli_runner().invoke(args=["send-daily-summary"])

    assert "Sent the summary for 1 business(es)." in result.output


def test_the_email_looks_ahead(client, admin, outbox):
    category = Category(name="Drinks")
    db.session.add(category)
    db.session.flush()
    tea = Product(
        sku="TEA-2",
        name="Tea bags",
        category_id=category.id,
        cost_price=Decimal("20"),
        selling_price=Decimal("50"),
        quantity=12,
        reorder_level=2,
        created_at=datetime.now(UTC) - timedelta(days=90),
    )
    db.session.add(tea)
    db.session.commit()
    for back in range(1, 30):
        ring(admin.user.id, tea, today() - timedelta(days=back), quantity=2)
    batch = MoneyImport(source="sms", added=0, duplicates=0, skipped=0, created_by=admin.user.id)
    batch.transactions.append(
        MoneyTransaction(
            receipt="RENT000009",
            occurred_at=at(today() - timedelta(days=3)),
            direction="out",
            amount=Decimal("20000"),
            kind="paybill",
            category="rent",
            counterparty="LANDLORD",
        )
    )
    db.session.add(batch)
    db.session.commit()

    client.post("/api/tasks/daily-summary", headers=TOKEN)

    body = outbox[-1]["body"]
    assert "Looking ahead" in body
    assert "Expected sales over the next 7 days: about KES 700.00" in body
    assert "  Tea bags: about 6 days left, order about 16" in body
    assert "Cash: more is likely to go out than come in over the next 30 days" in body


def test_without_history_there_is_nothing_to_look_ahead_to(client, admin, outbox):
    client.post("/api/tasks/daily-summary", headers=TOKEN)

    assert "Looking ahead" not in outbox[-1]["body"]
