from decimal import Decimal

import pytest

from app.extensions import db
from app.models import Category, Product, StockMovement, Supplier


@pytest.fixture()
def shop(app):
    category = Category(name="Grocery")
    db.session.add(category)
    db.session.flush()
    sugar = Product(
        sku="SP-7",
        name="Sugar",
        category_id=category.id,
        cost_price=Decimal("150"),
        selling_price=Decimal("190"),
        quantity=0,
    )
    rice = Product(
        sku="SP-8",
        name="Rice",
        category_id=category.id,
        cost_price=Decimal("120"),
        selling_price=Decimal("160"),
        quantity=5,
    )
    supplier = Supplier(name="Metro Wholesale")
    db.session.add_all([sugar, rice, supplier])
    db.session.commit()
    return {"sugar": sugar.id, "rice": rice.id, "supplier": supplier.id}


def stock(product_id):
    db.session.expire_all()
    return db.session.get(Product, product_id).quantity


def draft(buyer, shop, **extra):
    return buyer.post(
        "/api/purchases/",
        json={
            "supplier_id": shop["supplier"],
            "items": [
                {"product_id": shop["sugar"], "quantity": 10, "unit_cost": "150.00", "total": "1"},
                {"product_id": shop["rice"], "quantity": 4, "unit_cost": "120.00"},
            ],
            "total": "1.00",
            **extra,
        },
    )


def test_unknown_fields_like_a_browser_total_are_refused(as_role, shop):
    assert draft(as_role("procurement"), shop).status_code == 422


def make(buyer, shop, **extra):
    return buyer.post(
        "/api/purchases/",
        json={
            "supplier_id": shop["supplier"],
            "items": [
                {"product_id": shop["sugar"], "quantity": 10, "unit_cost": "150.00"},
                {"product_id": shop["rice"], "quantity": 4, "unit_cost": "120.00"},
            ],
            **extra,
        },
    )


def test_a_new_order_is_a_draft_until_confirmed(as_role, shop):
    buyer, store = as_role("procurement"), as_role("inventory")
    created = make(buyer, shop).json

    assert (created["reference"], created["status"], created["total"]) == (
        "PO-0001",
        "draft",
        "1980.00",
    )
    assert store.post(f"/api/purchases/{created['id']}/receive", json={}).status_code == 409

    edited = buyer.put(
        f"/api/purchases/{created['id']}",
        json={
            "supplier_id": shop["supplier"],
            "items": [{"product_id": shop["sugar"], "quantity": 20, "unit_cost": "150.00"}],
        },
    ).json
    assert edited["total"] == "3000.00"
    assert len(edited["items"]) == 1

    confirmed = buyer.post(f"/api/purchases/{created['id']}/confirm").json
    assert confirmed["status"] == "ordered"
    assert confirmed["ordered_at"]
    locked = buyer.put(
        f"/api/purchases/{created['id']}",
        json={
            "supplier_id": shop["supplier"],
            "items": [{"product_id": shop["sugar"], "quantity": 1, "unit_cost": "1"}],
        },
    )
    assert locked.status_code == 409


def test_inactive_suppliers_and_retired_products_get_no_new_orders(as_role, shop):
    buyer, admin = as_role("procurement"), as_role("admin")
    buyer.put(
        f"/api/suppliers/{shop['supplier']}", json={"name": "Metro Wholesale", "is_active": False}
    )
    assert make(buyer, shop).status_code == 409

    buyer.put(f"/api/suppliers/{shop['supplier']}", json={"name": "Metro Wholesale"})
    admin.post(f"/api/products/{shop['rice']}/retire")
    response = make(buyer, shop)
    assert response.status_code == 409
    assert "Rice" in response.json["error"]["message"]


def test_partial_deliveries_get_their_own_grn_and_complete_the_order(as_role, shop):
    buyer, store = as_role("procurement"), as_role("inventory")
    order = make(buyer, shop, confirm=True).json
    sugar_line, rice_line = order["items"]

    first = store.post(
        f"/api/purchases/{order['id']}/receive",
        json={
            "lines": [{"item_id": sugar_line["id"], "quantity": 6}],
            "idempotency_key": "grn-key-001",
        },
    ).json
    assert first["status"] == "partially_received"
    assert first["items"][0]["outstanding"] == 4
    assert first["receipts"][0]["reference"] == "GRN-0001"
    assert stock(shop["sugar"]) == 6

    too_many = store.post(
        f"/api/purchases/{order['id']}/receive",
        json={"lines": [{"item_id": sugar_line["id"], "quantity": 5}]},
    )
    assert too_many.status_code == 409
    assert "only 4 outstanding" in too_many.json["error"]["message"]
    assert stock(shop["sugar"]) == 6

    rest = store.post(f"/api/purchases/{order['id']}/receive", json={}).json  # all outstanding
    assert rest["status"] == "received"
    assert [r["reference"] for r in rest["receipts"]] == ["GRN-0001", "GRN-0002"]
    assert (stock(shop["sugar"]), stock(shop["rice"])) == (10, 9)
    ledger = db.session.scalars(db.select(StockMovement.reference).order_by(StockMovement.id)).all()
    assert ledger == ["GRN-0001", "GRN-0002", "GRN-0002"]


def test_a_repeated_receive_with_the_same_key_adds_nothing(as_role, shop):
    buyer, store = as_role("procurement"), as_role("inventory")
    order = make(buyer, shop, confirm=True).json
    body = {
        "lines": [{"item_id": order["items"][0]["id"], "quantity": 10}],
        "idempotency_key": "double-click-1",
    }

    first = store.post(f"/api/purchases/{order['id']}/receive", json=body)
    second = store.post(f"/api/purchases/{order['id']}/receive", json=body)

    assert first.status_code == second.status_code == 200
    assert stock(shop["sugar"]) == 10  # +10 once, not +20
    assert len(second.json["receipts"]) == 1


def test_a_linked_request_is_fulfilled_when_the_order_arrives(as_role, shop, outbox):
    employee, buyer, store = as_role("employee"), as_role("procurement"), as_role("inventory")
    request_id = employee.post(
        "/api/requests/", json={"item": "Sugar", "quantity": 10, "reason": "Kitchen"}
    ).json["id"]

    pending_link = make(buyer, shop, request_id=request_id)
    assert pending_link.status_code == 409

    buyer.post(f"/api/requests/{request_id}/approve", json={})
    order = make(buyer, shop, request_id=request_id, confirm=True).json
    assert order["request_reference"] == "REQ-0001"
    store.post(f"/api/purchases/{order['id']}/receive", json={})

    request = employee.get(f"/api/requests/{request_id}").json
    assert request["status"] == "fulfilled"
    assert request["purchases"][0]["reference"] == "PO-0001"
    timeline = [
        e["action"] for e in employee.get(f"/api/requests/{request_id}/timeline").json["results"]
    ]
    assert timeline == ["Fulfilled", "Note", "Linked", "Approved", "Submitted"]
    assert outbox[-1]["subject"] == "Your request REQ-0001 is ready"


def test_cancelling_needs_a_reason_and_only_before_anything_arrives(as_role, shop):
    buyer, store = as_role("procurement"), as_role("inventory")
    order = make(buyer, shop, confirm=True).json
    store.post(
        f"/api/purchases/{order['id']}/receive",
        json={"lines": [{"item_id": order["items"][0]["id"], "quantity": 1}]},
    )
    other = make(buyer, shop).json

    late = buyer.post(f"/api/purchases/{order['id']}/cancel", json={"reason": "Too slow"})
    no_reason = buyer.post(f"/api/purchases/{other['id']}/cancel", json={})
    ok = buyer.post(f"/api/purchases/{other['id']}/cancel", json={"reason": "Ordered elsewhere"})

    assert late.status_code == 409
    assert no_reason.status_code == 422
    assert ok.json["status"] == "cancelled"
    assert ok.json["cancel_reason"] == "Ordered elsewhere"


def test_awaiting_filter_lists_ordered_and_partly_received(as_role, shop):
    buyer, store = as_role("procurement"), as_role("inventory")
    make(buyer, shop)  # draft
    make(buyer, shop, confirm=True)
    partly = make(buyer, shop, confirm=True).json
    store.post(
        f"/api/purchases/{partly['id']}/receive",
        json={"lines": [{"item_id": partly["items"][0]["id"], "quantity": 1}]},
    )

    awaiting = buyer.get("/api/purchases/?status=awaiting").json
    found = buyer.get("/api/purchases/?search=po-0003").json["results"]

    assert awaiting["count"] == 2
    assert [p["reference"] for p in found] == ["PO-0003"]
