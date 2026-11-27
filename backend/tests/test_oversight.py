from decimal import Decimal

import pytest

from app.extensions import db
from app.models import (
    AuditLog,
    Category,
    Notification,
    Product,
    Purchase,
    Supplier,
    User,
)
from tests.conftest import PASSWORD


@pytest.fixture()
def approval(app):
    app.config["STAFF_APPROVAL_REQUIRED"] = True
    yield app
    app.config["STAFF_APPROVAL_REQUIRED"] = False


def join(client, email="grace@test.com"):
    return client.post(
        "/api/auth/register",
        json={
            "full_name": "Grace Wanjiru",
            "email": email,
            "password": PASSWORD,
            "join_code": "TESTJOIN",
        },
    )


def sign_in(client, email="grace@test.com"):
    return client.post("/api/auth/login", json={"email": email, "password": PASSWORD})


@pytest.fixture()
def stocked():
    category = Category(name="Grocery")
    db.session.add(category)
    db.session.flush()
    supplier = Supplier(name="Metro Wholesale")
    db.session.add(supplier)
    db.session.flush()
    sugar = Product(
        sku="SUG",
        name="Sugar",
        category_id=category.id,
        cost_price=Decimal("100.00"),
        selling_price=Decimal("150.00"),
        quantity=12,
        reorder_level=10,
        default_supplier_id=supplier.id,
    )
    salt = Product(
        sku="SLT",
        name="Salt",
        category_id=category.id,
        cost_price=Decimal("20.00"),
        selling_price=Decimal("40.00"),
        quantity=6,
        reorder_level=5,
        reorder_quantity=24,
        default_supplier_id=supplier.id,
    )
    rice = Product(
        sku="RCE",
        name="Rice",
        category_id=category.id,
        cost_price=Decimal("90.00"),
        selling_price=Decimal("120.00"),
        quantity=3,
        reorder_level=2,
    )
    db.session.add_all([sugar, salt, rice])
    db.session.commit()
    return {"supplier": supplier.id, "sugar": sugar.id, "salt": salt.id, "rice": rice.id}


def sell(client, product_id, quantity):
    return client.post(
        "/api/sales/",
        json={
            "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": quantity}],
        },
    )


def drafts():
    return db.session.scalars(db.select(Purchase).order_by(Purchase.id)).all()


def test_new_staff_wait_for_the_admin(approval, client, admin, outbox):
    joined = join(client)
    refused = sign_in(client)

    assert joined.status_code == 201
    assert "your administrator will approve your account" in joined.json["message"]
    assert refused.status_code == 403
    assert refused.json["error"]["reason"] == "awaiting_approval"
    assert outbox[-1]["to"] == admin.user.email
    assert "Grace Wanjiru is waiting for approval" in outbox[-1]["subject"]
    waiting = admin.get("/api/users/?pending=true").json["results"]
    assert [(u["email"], u["is_approved"]) for u in waiting] == [("grace@test.com", False)]


def test_approving_sets_the_role_and_lets_them_in(approval, client, admin, outbox):
    join(client)
    grace_id = db.session.scalar(db.select(User.id).filter_by(email="grace@test.com"))

    approved = admin.post(f"/api/users/{grace_id}/approve", json={"role": "sales"})
    again = admin.post(f"/api/users/{grace_id}/approve", json={"role": "sales"})
    signed_in = sign_in(client)

    assert (approved.json["role"], approved.json["is_approved"]) == ("sales", True)
    assert again.status_code == 409
    assert signed_in.status_code == 200
    assert signed_in.json["user"]["role"] == "sales"
    assert outbox[-1]["subject"] == "Your StockPilot account is approved"
    entry = db.session.scalars(db.select(AuditLog).order_by(AuditLog.id.desc())).first()
    assert entry.summary == "Grace Wanjiru approved as Sales Attendant"


def test_declining_removes_the_request(approval, client, admin):
    join(client)
    grace = db.session.scalar(db.select(User).filter_by(email="grace@test.com"))

    assert admin.post(f"/api/users/{grace.id}/decline").status_code == 204
    assert db.session.scalar(db.select(User).filter_by(email="grace@test.com")) is None
    assert sign_in(client).status_code == 401


def test_waiting_staff_hold_no_role_and_get_no_notices(admin, as_role, make_user):
    waiting = make_user("procurement", approved=False)

    as_role("employee").post(
        "/api/requests/", json={"item": "Pens", "quantity": 1, "reason": "Out of pens"}
    )

    assert admin.get("/api/auth/me").json["covers"] == ["procurement", "inventory", "sales"]
    notified = db.session.scalars(db.select(Notification.user_id)).all()
    assert notified == [admin.user.id]
    assert waiting.id not in notified


def test_admin_covers_a_job_only_until_someone_holds_it(admin, make_user, stocked):
    covering = sell(admin, stocked["rice"], 1)
    make_user("sales")
    refused = sell(admin, stocked["rice"], 1)

    assert covering.status_code == 201
    assert refused.status_code == 403
    assert "Sales staff handle this" in refused.json["error"]["message"]
    assert admin.get("/api/auth/me").json["covers"] == ["procurement", "inventory"]


def test_other_roles_cover_nothing(as_role):
    assert as_role("sales").get("/api/auth/me").json["covers"] == []


def test_attendants_void_their_own_sales_and_the_admin_hears(as_role, admin, stocked):
    seller, other = as_role("sales"), as_role("sales")
    sale = sell(seller, stocked["sugar"], 1).json

    blocked = other.post(f"/api/sales/{sale['id']}/void", json={"reason": "Mistake"})
    voided = seller.post(f"/api/sales/{sale['id']}/void", json={"reason": "Mistake"})

    assert blocked.status_code == 403
    assert voided.json["status"] == "voided"
    notes = db.session.scalars(
        db.select(Notification.message).where(Notification.user_id == admin.user.id)
    ).all()
    assert notes == [f"{seller.user.full_name} voided S-0001 (150.00): Mistake"]


def test_receiving_averages_the_cost_price(as_role, stocked):
    buyer, store = as_role("procurement"), as_role("inventory")
    order = buyer.post(
        "/api/purchases/",
        json={
            "supplier_id": stocked["supplier"],
            "items": [{"product_id": stocked["sugar"], "quantity": 4, "unit_cost": "130.00"}],
            "confirm": True,
        },
    ).json

    store.post(f"/api/purchases/{order['id']}/receive")

    sugar = store.get(f"/api/products/{stocked['sugar']}").json
    assert (sugar["quantity"], sugar["cost_price"]) == (16, "107.50")
    entry = db.session.scalars(
        db.select(AuditLog).where(AuditLog.entity_type == "product").order_by(AuditLog.id.desc())
    ).first()
    assert entry.changes == {"cost_price": ["100.00", "107.50"]}


def test_cost_starts_from_the_price_paid_when_nothing_is_left(as_role, stocked):
    rice = db.session.get(Product, stocked["rice"])
    rice.quantity, rice.default_supplier_id = 0, stocked["supplier"]
    db.session.commit()
    buyer, store = as_role("procurement"), as_role("inventory")
    order = buyer.post(
        "/api/purchases/",
        json={
            "supplier_id": stocked["supplier"],
            "items": [{"product_id": stocked["rice"], "quantity": 10, "unit_cost": "95.00"}],
            "confirm": True,
        },
    ).json

    store.post(f"/api/purchases/{order['id']}/receive")

    assert store.get(f"/api/products/{stocked['rice']}").json["cost_price"] == "95.00"


def test_low_stock_prepares_one_draft_per_supplier(as_role, stocked):
    seller, buyer = as_role("sales"), as_role("procurement")

    sell(seller, stocked["sugar"], 3)
    sell(seller, stocked["salt"], 2)
    sell(seller, stocked["sugar"], 1)

    [draft] = drafts()
    assert (draft.status, draft.source, draft.supplier_id) == (
        "draft",
        "low_stock",
        stocked["supplier"],
    )
    lines = {line.product.name: line.quantity for line in draft.items}
    assert lines == {"Sugar": 11, "Salt": 24}
    assert draft.total == Decimal("1580.00")
    notes = db.session.scalars(
        db.select(Notification.message).where(Notification.user_id == buyer.user.id)
    ).all()
    assert notes[0] == "Sugar is low on stock (9 left). It was added to PO-0001, ready to confirm."
    assert buyer.post(f"/api/purchases/{draft.id}/confirm").json["status"] == "ordered"


def test_no_draft_without_a_default_supplier(as_role, stocked):
    sell(as_role("sales"), stocked["rice"], 2)

    assert drafts() == []


def test_no_second_draft_while_the_product_is_on_order(as_role, stocked):
    buyer = as_role("procurement")
    buyer.post(
        "/api/purchases/",
        json={
            "supplier_id": stocked["supplier"],
            "items": [{"product_id": stocked["sugar"], "quantity": 5, "unit_cost": "100"}],
            "confirm": True,
        },
    )

    sell(as_role("sales"), stocked["sugar"], 3)

    assert [p.source for p in drafts()] == ["manual"]


def test_an_approved_request_becomes_a_draft_order(as_role, stocked):
    employee, buyer = as_role("employee"), as_role("procurement")
    asked = employee.post(
        "/api/requests/",
        json={"item": "Salt", "quantity": 30, "reason": "Kitchen", "product_id": stocked["salt"]},
    ).json

    buyer.post(f"/api/requests/{asked['id']}/approve", json={})

    [draft] = drafts()
    assert (draft.source, draft.request_id, draft.status) == ("request", asked["id"], "draft")
    assert [(line.product_id, line.quantity) for line in draft.items] == [(stocked["salt"], 30)]


def test_a_request_without_a_supplier_waits_for_procurement(as_role, stocked):
    employee, buyer = as_role("employee"), as_role("procurement")
    asked = employee.post(
        "/api/requests/",
        json={"item": "Rice", "quantity": 3, "reason": "Kitchen", "product_id": stocked["rice"]},
    ).json

    buyer.post(f"/api/requests/{asked['id']}/approve", json={})

    assert drafts() == []


def test_products_remember_their_supplier_and_order_size(as_role, stocked):
    store = as_role("inventory")
    sugar = store.get(f"/api/products/{stocked['sugar']}").json

    changed = store.put(
        f"/api/products/{stocked['sugar']}",
        json={
            **{k: sugar[k] for k in ("sku", "name", "category_id")},
            "cost_price": "100.00",
            "selling_price": "150.00",
            "reorder_level": 10,
            "reorder_quantity": 50,
            "default_supplier_id": stocked["supplier"],
        },
    )
    unknown = store.put(
        f"/api/products/{stocked['sugar']}",
        json={
            **{k: sugar[k] for k in ("sku", "name", "category_id")},
            "cost_price": "100.00",
            "selling_price": "150.00",
            "default_supplier_id": 999,
        },
    )

    assert sugar["default_supplier_name"] == "Metro Wholesale"
    assert changed.json["reorder_quantity"] == 50
    assert unknown.status_code == 400


def test_procurement_can_add_a_product_while_ordering(as_role, stocked):
    buyer = as_role("procurement")
    category_id = db.session.get(Product, stocked["sugar"]).category_id

    created = buyer.post(
        "/api/products/",
        json={
            "sku": "FLR",
            "name": "Flour",
            "category_id": category_id,
            "cost_price": "70.00",
            "selling_price": "95.00",
            "default_supplier_id": stocked["supplier"],
        },
    )

    assert created.status_code == 201
    assert created.json["quantity"] == 0
