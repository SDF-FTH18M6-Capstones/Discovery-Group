from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import Category, Notification, Product, Sale, StockMovement


@pytest.fixture()
def water(app):
    category = Category(name="Beverages")
    db.session.add(category)
    db.session.flush()
    product = Product(
        sku="SP-1",
        name="Water",
        category_id=category.id,
        cost_price=Decimal("180.00"),
        selling_price=Decimal("250.00"),
        quantity=10,
        reorder_level=5,
    )
    db.session.add(product)
    db.session.commit()
    return product


def sell(client, product_id, quantity=1, key=None):
    body = {"payment_method": "cash", "items": [{"product_id": product_id, "quantity": quantity}]}
    if key:
        body["idempotency_key"] = key
    return client.post("/api/sales/", json=body)


def stock(product_id):
    db.session.expire_all()
    return db.session.get(Product, product_id).quantity


def test_receipt_numbers_and_vat_included_in_prices(as_role, water):
    sale = sell(as_role("sales"), water.id, 2).json

    assert sale["receipt_number"] == "S-0001"
    assert sale["total"] == "500.00"
    assert sale["vat_rate"] == "16.00"
    assert sale["vat_amount"] == "68.97"
    assert sale["net_amount"] == "431.03"


def test_the_same_idempotency_key_sells_once(as_role, water):
    seller = as_role("sales")

    first = sell(seller, water.id, 2, key="till-1-0001")
    again = sell(seller, water.id, 2, key="till-1-0001")

    assert first.status_code == again.status_code == 201
    assert again.json["id"] == first.json["id"]
    assert stock(water.id) == 8
    assert db.session.scalar(db.select(db.func.count(Sale.id))) == 1


def test_profit_uses_the_cost_at_the_time_of_sale(as_role, water):
    sell(as_role("sales"), water.id, 2)
    admin = as_role("admin")
    product = admin.get(f"/api/products/{water.id}").json
    admin.put(
        f"/api/products/{water.id}",
        json={
            **{
                k: product[k]
                for k in ("sku", "name", "category_id", "selling_price", "reorder_level")
            },
            "cost_price": "240.00",
        },
    )

    report = admin.get("/api/reports/summary?days=1").json

    assert report["gross_profit"] == "140.00"
    assert report["cost_of_sales"] == "360.00"


def test_a_retired_product_cannot_be_sold_and_leaves_the_till(as_role, water):
    admin = as_role("admin")
    assert admin.post(f"/api/products/{water.id}/retire").json["is_active"] is False

    response = sell(as_role("sales"), water.id)

    assert response.status_code == 409
    assert "No longer sold" in response.json["error"]["message"]
    assert admin.get("/api/products/").json["count"] == 0
    assert admin.get("/api/products/?status=retired").json["count"] == 1
    admin.post(f"/api/products/{water.id}/restore")
    assert sell(as_role("sales"), water.id).status_code == 201


def test_voiding_a_sale_returns_stock_and_keeps_the_record(as_role, water):
    sale = sell(as_role("sales"), water.id, 3).json
    admin = as_role("admin")

    no_reason = admin.post(f"/api/sales/{sale['id']}/void", json={})
    voided = admin.post(f"/api/sales/{sale['id']}/void", json={"reason": "Rang up twice"})
    twice = admin.post(f"/api/sales/{sale['id']}/void", json={"reason": "Again"})

    assert no_reason.status_code == 422
    assert voided.status_code == 200
    assert voided.json["status"] == "voided"
    assert voided.json["void_reason"] == "Rang up twice"
    assert twice.status_code == 409
    assert stock(water.id) == 10
    ledger = db.session.scalars(
        db.select(StockMovement).order_by(StockMovement.id.desc()).limit(1)
    ).one()
    assert (ledger.type, ledger.change, ledger.reference) == ("sale_void", 3, "S-0001")
    report = admin.get("/api/reports/summary?days=1").json
    assert (report["sales_count"], report["voided_count"]) == (0, 1)


def test_only_todays_sales_can_be_voided(as_role, water):
    sale = sell(as_role("sales"), water.id).json
    row = db.session.get(Sale, sale["id"])
    row.created_at = datetime.now(UTC) - timedelta(days=2)
    db.session.commit()

    response = as_role("admin").post(f"/api/sales/{sale['id']}/void", json={"reason": "Mistake"})

    assert response.status_code == 409
    assert response.json["error"]["message"] == "Only today's sales can be voided."


def test_sales_can_be_found_by_receipt_number_and_attendant(as_role, water):
    seller, other = as_role("sales"), as_role("sales")
    sell(seller, water.id)
    sell(other, water.id)
    admin = as_role("admin")

    by_number = admin.get("/api/sales/?search=S-0002").json["results"]
    by_attendant = admin.get(f"/api/sales/?attendant_id={seller.user.id}").json["results"]

    assert [s["receipt_number"] for s in by_number] == ["S-0002"]
    assert [s["attendant_id"] for s in by_attendant] == [seller.user.id]


def low_stock_alerts():
    return db.session.scalars(
        db.select(Notification.message).where(Notification.message.like("Water%"))
    ).all()


def test_low_stock_alerts_fire_once_when_crossing(as_role, water, outbox):
    as_role("inventory")
    seller = as_role("sales")

    sell(seller, water.id, 4)
    assert low_stock_alerts() == []
    sell(seller, water.id, 2)
    sell(seller, water.id, 1)
    sell(seller, water.id, 3)

    assert low_stock_alerts() == ["Water is low on stock (4 left).", "Water is out of stock."]
    assert [e["subject"] for e in outbox] == ["Low stock: Water", "Low stock: Water"]
