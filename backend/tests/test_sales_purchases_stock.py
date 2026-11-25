from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.extensions import db
from app.models import Category, Notification, Product, Sale, StockMovement, Supplier


@pytest.fixture()
def shop(app):
    beverages = Category(name="Beverages")
    db.session.add(beverages)
    db.session.flush()
    water = Product(
        sku="SP-001",
        name="Water",
        category_id=beverages.id,
        cost_price=Decimal("180"),
        selling_price=Decimal("250"),
        quantity=10,
        reorder_level=3,
    )
    tea = Product(
        sku="SP-002",
        name="Tea",
        category_id=beverages.id,
        cost_price=Decimal("40"),
        selling_price=Decimal("60"),
        quantity=2,
        reorder_level=1,
    )
    supplier = Supplier(name="Metro Wholesale")
    db.session.add_all([water, tea, supplier])
    db.session.commit()
    return {"water": water.id, "tea": tea.id, "supplier": supplier.id}


def stock(product_id):
    db.session.expire_all()
    return db.session.get(Product, product_id).quantity


def sell(client, lines, payment="mpesa"):
    items = [{"product_id": pid, "quantity": qty} for pid, qty in lines]
    return client.post("/api/sales/", json={"payment_method": payment, "items": items})


def test_a_sale_takes_prices_from_the_server_and_reduces_stock(as_role, shop):
    seller = as_role("sales")

    response = sell(seller, [(shop["water"], 2)], payment="cash")

    assert response.status_code == 201
    sale = response.json
    assert sale["receipt_number"] == f"S-{sale['id']:04d}"
    assert sale["total"] == "500.00"
    assert sale["items"][0]["unit_price"] == "250.00"
    assert sale["items"][0]["line_total"] == "500.00"
    assert stock(shop["water"]) == 8
    movement = db.session.scalar(db.select(StockMovement).where(StockMovement.type == "sale"))
    assert movement.change == -2


def test_the_browser_cannot_set_its_own_price(as_role, shop):
    response = as_role("sales").post(
        "/api/sales/",
        json={
            "payment_method": "cash",
            "items": [{"product_id": shop["water"], "quantity": 2, "unit_price": "1.00"}],
        },
    )

    assert response.status_code == 422
    assert stock(shop["water"]) == 10


def test_the_same_product_twice_becomes_one_line(as_role, shop):
    response = sell(as_role("sales"), [(shop["water"], 1), (shop["water"], 2)])

    assert [line["quantity"] for line in response.json["items"]] == [3]


def test_not_enough_stock_refuses_the_whole_sale(as_role, shop):
    response = sell(as_role("sales"), [(shop["water"], 1), (shop["tea"], 5)])

    assert response.status_code == 409
    assert response.json["error"]["message"] == "Not enough stock: Tea (2 left)."
    assert stock(shop["water"]) == 10
    assert db.session.scalar(db.select(db.func.count()).select_from(StockMovement)) == 0


@pytest.mark.parametrize(
    "body, field",
    [
        (
            {"payment_method": "bitcoin", "items": [{"product_id": 1, "quantity": 1}]},
            "payment_method",
        ),
        ({"payment_method": "cash", "items": []}, "items"),
        ({"payment_method": "cash"}, "items"),
        ({"payment_method": "cash", "items": [{"product_id": 1, "quantity": 0}]}, "items"),
    ],
)
def test_bad_sales_are_422(as_role, shop, body, field):
    response = as_role("sales").post("/api/sales/", json=body)

    assert response.status_code == 422
    assert field in response.json["error"]["details"]


def test_unknown_product_is_400(as_role, shop):
    assert sell(as_role("sales"), [(999999, 1)]).status_code == 400


def test_selling_to_the_reorder_level_warns_inventory(as_role, make_user, shop):
    inventory = make_user("inventory")

    sell(as_role("sales"), [(shop["tea"], 1)])

    messages = db.session.scalars(
        db.select(Notification.message).where(Notification.user_id == inventory.id)
    ).all()
    assert messages == ["Tea is low on stock (1 left)."]


def test_attendants_see_only_their_own_sales_and_admin_sees_all(as_role, shop):
    vincent, other, admin = as_role("sales"), as_role("sales"), as_role("admin")
    mine = sell(vincent, [(shop["water"], 1)]).json["id"]
    theirs = sell(other, [(shop["water"], 1)]).json["id"]

    assert [s["id"] for s in vincent.get("/api/sales/").json["results"]] == [mine]
    assert vincent.get(f"/api/sales/{theirs}").status_code == 404
    assert admin.get("/api/sales/").json["count"] == 2


def order(client, shop, quantity=12, confirm=True):
    return client.post(
        "/api/purchases/",
        json={
            "supplier_id": shop["supplier"],
            "items": [{"product_id": shop["water"], "quantity": quantity, "unit_cost": "180.00"}],
            "confirm": confirm,
        },
    )


def test_ordering_does_not_change_stock_but_receiving_does_once(as_role, shop):
    buyer, store = as_role("procurement"), as_role("inventory")

    created = order(buyer, shop)
    assert created.status_code == 201
    assert created.json["status"] == "ordered"
    assert created.json["total"] == "2160.00"
    assert created.json["reference"] == f"PO-{created.json['id']:04d}"
    assert stock(shop["water"]) == 10

    received = store.post(f"/api/purchases/{created.json['id']}/receive")
    assert received.status_code == 200
    assert received.json["status"] == "received"
    assert stock(shop["water"]) == 22

    again = store.post(f"/api/purchases/{created.json['id']}/receive")
    assert again.status_code == 409
    assert again.json["error"]["message"] == "This order is already received."
    assert stock(shop["water"]) == 22


def test_receiving_tells_the_buyer(as_role, shop):
    buyer = as_role("procurement")
    purchase_id = order(buyer, shop).json["id"]

    as_role("inventory").post(f"/api/purchases/{purchase_id}/receive")

    notes = db.session.scalars(
        db.select(Notification.message).where(Notification.user_id == buyer.user.id)
    ).all()
    assert notes == ["PO-0001 was received in full (GRN-0001)."]


def test_a_cancelled_order_cannot_be_received(as_role, shop):
    purchase_id = order(as_role("procurement"), shop).json["id"]
    assert (
        as_role("admin")
        .post(f"/api/purchases/{purchase_id}/cancel", json={"reason": "Supplier closed"})
        .json["status"]
        == "cancelled"
    )

    response = as_role("inventory").post(f"/api/purchases/{purchase_id}/receive")

    assert response.status_code == 409
    assert stock(shop["water"]) == 10


def test_unknown_supplier_or_product_is_400(as_role, shop):
    buyer = as_role("procurement")
    bad_supplier = {
        "supplier_id": 999,
        "items": [{"product_id": shop["water"], "quantity": 1, "unit_cost": "1"}],
    }
    bad_product = {
        "supplier_id": shop["supplier"],
        "items": [{"product_id": 999, "quantity": 1, "unit_cost": "1"}],
    }

    assert buyer.post("/api/purchases/", json=bad_supplier).status_code == 400
    assert buyer.post("/api/purchases/", json=bad_product).status_code == 400


def test_purchases_filter_by_status(as_role, shop):
    buyer = as_role("procurement")
    order(buyer, shop)
    cancelled = order(buyer, shop).json["id"]
    buyer.post(f"/api/purchases/{cancelled}/cancel", json={"reason": "Ordered twice"})

    assert buyer.get("/api/purchases/?status=ordered").json["count"] == 1
    assert buyer.get("/api/purchases/?status=cancelled").json["count"] == 1


def test_adjustments_change_stock_with_a_reason(as_role, shop):
    store = as_role("inventory")

    response = store.post(
        "/api/stock/adjustments",
        json={"product_id": shop["water"], "change": -2, "reason": "  Damaged in transit  "},
    )

    assert response.status_code == 201
    assert response.json["reason"] == "Damaged in transit"
    assert response.json["balance_now"] == 8
    assert stock(shop["water"]) == 8


def test_an_adjustment_cannot_take_stock_below_zero(as_role, shop):
    response = as_role("inventory").post(
        "/api/stock/adjustments", json={"product_id": shop["tea"], "change": -3, "reason": "Lost"}
    )

    assert response.status_code == 409
    assert response.json["error"]["message"] == "Only 2 Tea in stock; cannot remove more."
    assert stock(shop["tea"]) == 2


@pytest.mark.parametrize(
    "body, field",
    [
        ({"change": 0, "reason": "Nothing"}, "change"),
        ({"change": 1, "reason": "  "}, "reason"),
        ({"change": 1}, "reason"),
    ],
)
def test_bad_adjustments_are_422(as_role, shop, body, field):
    response = as_role("inventory").post(
        "/api/stock/adjustments", json={"product_id": shop["water"], **body}
    )

    assert response.status_code == 422
    assert field in response.json["error"]["details"]


def test_the_ledger_lists_every_change_newest_first_and_filters(as_role, shop):
    store = as_role("inventory")
    sell(as_role("sales"), [(shop["water"], 1)])
    store.post(
        "/api/stock/adjustments", json={"product_id": shop["tea"], "change": 4, "reason": "Recount"}
    )

    everything = store.get("/api/stock/movements").json["results"]
    water_only = store.get(f"/api/stock/movements?product_id={shop['water']}").json["results"]
    sales_only = store.get("/api/stock/movements?type=sale").json["results"]

    assert [(m["product_name"], m["change"]) for m in everything] == [("Tea", 4), ("Water", -1)]
    assert [m["type"] for m in water_only] == ["sale"]
    assert [m["product_name"] for m in sales_only] == ["Water"]


def test_day_filter_uses_the_shop_clock(as_role):
    nairobi = ZoneInfo("Africa/Nairobi")
    today = datetime.now(nairobi).date()
    admin = as_role("admin")
    for when, total in (
        (datetime.combine(today, time(0, 30), tzinfo=nairobi), "100"),
        (datetime.combine(today - timedelta(days=1), time(23, 30), tzinfo=nairobi), "50"),
    ):
        db.session.add(
            Sale(
                attendant_id=admin.user.id,
                payment_method="cash",
                total=Decimal(total),
                created_at=when,
            )
        )
    db.session.commit()

    response = admin.get(f"/api/sales/?day={today.isoformat()}")

    assert [sale["total"] for sale in response.json["results"]] == ["100.00"]
