from decimal import Decimal

import pytest

from app import mpesa
from app.extensions import db
from app.models import Business, Category, Notification, Product, Purchase, Supplier
from app.vault import seal, unseal

SANDBOX = {
    "mode": "sandbox",
    "type": "paybill",
    "shortcode": "174379",
    "passkey": "my-passkey",
    "consumer_key": "my-key",
    "consumer_secret": "my-secret",
}


def test_a_business_starts_without_its_own_till(admin):
    settings = admin.get("/api/business/mpesa").json

    assert settings == {
        "mode": "simulate",
        "type": "paybill",
        "shortcode": None,
        "till": None,
        "has_passkey": False,
        "has_keys": False,
    }


def test_real_payments_need_every_detail(admin):
    refused = admin.put("/api/business/mpesa", json={"mode": "live", "type": "till"})

    assert refused.status_code == 422
    assert refused.json["error"]["message"] == (
        "To take real M-Pesa payments, add the Paybill or store number, till number, passkey, "
        "consumer key, consumer secret."
    )


def test_keys_are_stored_sealed_and_never_shown(admin, business):
    saved = admin.put("/api/business/mpesa", json=SANDBOX).json

    db.session.expire_all()
    stored = db.session.get(Business, business.id)
    assert saved == {
        "mode": "sandbox",
        "type": "paybill",
        "shortcode": "174379",
        "till": None,
        "has_passkey": True,
        "has_keys": True,
    }
    assert stored.mpesa_consumer_secret != "my-secret"
    assert unseal(stored.mpesa_consumer_secret) == "my-secret"


def test_blank_keys_keep_the_saved_ones(admin, business):
    admin.put("/api/business/mpesa", json=SANDBOX)

    kept = admin.put(
        "/api/business/mpesa",
        json={**SANDBOX, "passkey": "", "consumer_key": "", "consumer_secret": ""},
    )

    assert kept.status_code == 200
    db.session.expire_all()
    assert unseal(db.session.get(Business, business.id).mpesa_consumer_key) == "my-key"


def test_a_till_sends_buy_goods_requests(admin, business):
    admin.put(
        "/api/business/mpesa",
        json={**SANDBOX, "type": "till", "shortcode": "600200", "till": "123456"},
    )
    db.session.expire_all()

    account = mpesa.business_account(db.session.get(Business, business.id))

    assert (account.transaction_type, account.shortcode, account.party_b) == (
        "CustomerBuyGoodsOnline",
        "600200",
        "123456",
    )


def test_sales_never_fall_back_to_stockpilots_paybill(app, business):
    app.config.update(MPESA_MODE="live", MPESA_CONSUMER_KEY="platform", MPESA_CONSUMER_SECRET="x")
    try:
        with app.app_context():
            account = mpesa.business_account(business)
    finally:
        app.config.update(MPESA_MODE="simulate", MPESA_CONSUMER_KEY="", MPESA_CONSUMER_SECRET="")

    assert account.mode == "off"


def test_each_business_uses_its_own_keys(admin, business, other_business):
    admin.put("/api/business/mpesa", json=SANDBOX)
    db.session.expire_all()

    mine = mpesa.business_account(db.session.get(Business, business.id))
    theirs = mpesa.business_account(db.session.get(Business, other_business))

    assert mine.consumer_key == "my-key"
    assert theirs.mode == "simulate"
    assert theirs.consumer_key == ""


def test_sealed_values_need_the_right_key(app):
    with app.app_context():
        token = seal("secret")
        app.config["DATA_KEY"] = "another key"
        try:
            assert unseal(token) == ""
        finally:
            app.config["DATA_KEY"] = ""
        assert unseal(token) == "secret"
        assert seal("") is None


@pytest.fixture()
def other_business(app):
    other = Business(name="Other Shop", join_code="OTHER123")
    db.session.add(other)
    db.session.commit()
    return other.id


@pytest.fixture()
def shelf():
    category = Category(name="Grocery")
    db.session.add(category)
    db.session.flush()
    trusted = Supplier(name="Metro", email="orders@metro.test", trusted=True)
    careful = Supplier(name="Corner Wholesale", email="corner@test.test")
    db.session.add_all([trusted, careful])
    db.session.flush()
    sugar = Product(
        sku="SUG",
        name="Sugar",
        category_id=category.id,
        cost_price=Decimal("100"),
        selling_price=Decimal("150"),
        quantity=12,
        reorder_level=10,
        reorder_quantity=20,
        default_supplier_id=trusted.id,
    )
    salt = Product(
        sku="SLT",
        name="Salt",
        category_id=category.id,
        cost_price=Decimal("20"),
        selling_price=Decimal("40"),
        quantity=6,
        reorder_level=5,
        default_supplier_id=careful.id,
    )
    db.session.add_all([sugar, salt])
    db.session.commit()
    return {"trusted": trusted.id, "careful": careful.id, "sugar": sugar.id, "salt": salt.id}


def sell(client, product_id, quantity):
    return client.post(
        "/api/sales/",
        json={
            "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": quantity}],
        },
    )


def test_trusted_suppliers_get_low_stock_orders_straight_away(as_role, admin, shelf, outbox):
    seller, buyer, store = as_role("sales"), as_role("procurement"), as_role("inventory")
    admin.put(
        "/api/business",
        json={
            **{
                k: admin.get("/api/business").json[k]
                for k in ("name", "timezone", "currency", "vat_rate", "phone", "email")
            },
            "address": "Moi Avenue, Nairobi",
            "receipt_footer": None,
        },
    )

    sell(seller, shelf["sugar"], 3)

    [order] = db.session.scalars(db.select(Purchase)).all()
    assert (order.status, order.source, order.supplier_id) == (
        "ordered",
        "low_stock",
        shelf["trusted"],
    )
    assert order.ordered_at is not None
    [email] = [mail for mail in outbox if mail["to"] == "orders@metro.test"]
    assert email["subject"] == "Purchase order PO-0001 from Test Shop"
    assert "  20 x Sugar (SUG)" in email["body"]
    assert "Please deliver to: Moi Avenue, Nairobi" in email["body"]
    for person in (buyer, store):
        notes = db.session.scalars(
            db.select(Notification.message).where(Notification.user_id == person.user.id)
        ).all()
        assert any("PO-0001 was sent to Metro automatically" in note for note in notes)


def test_other_suppliers_still_wait_for_procurement(as_role, shelf, outbox):
    sell(as_role("sales"), shelf["salt"], 2)

    [order] = db.session.scalars(db.select(Purchase)).all()
    assert order.status == "draft"
    assert all(mail["to"] != "corner@test.test" for mail in outbox)


def test_placing_an_order_by_hand_emails_the_supplier(as_role, shelf, outbox):
    buyer = as_role("procurement")

    buyer.post(
        "/api/purchases/",
        json={
            "supplier_id": shelf["careful"],
            "items": [{"product_id": shelf["salt"], "quantity": 4, "unit_cost": "20"}],
            "confirm": True,
        },
    )

    assert outbox[-1]["to"] == "corner@test.test"
    assert "  4 x Salt (SLT)" in outbox[-1]["body"]


def test_suppliers_without_email_still_get_the_order_recorded(as_role, shelf, outbox):
    supplier = db.session.get(Supplier, shelf["trusted"])
    supplier.email = None
    db.session.commit()

    sell(as_role("sales"), shelf["sugar"], 3)

    assert db.session.scalar(db.select(Purchase.status)) == "ordered"
    assert all(mail["subject"].startswith("Purchase order") is False for mail in outbox)


def test_an_approved_request_goes_straight_to_a_trusted_supplier(as_role, shelf):
    employee, buyer = as_role("employee"), as_role("procurement")
    asked = employee.post(
        "/api/requests/",
        json={"item": "Sugar", "quantity": 5, "reason": "Kitchen", "product_id": shelf["sugar"]},
    ).json

    buyer.post(f"/api/requests/{asked['id']}/approve", json={})

    [order] = db.session.scalars(db.select(Purchase)).all()
    assert (order.status, order.source, order.request_id) == ("ordered", "request", asked["id"])


def test_procurement_decides_who_is_trusted(as_role, shelf):
    buyer = as_role("procurement")
    current = buyer.get(f"/api/suppliers/{shelf['careful']}").json

    changed = buyer.put(
        f"/api/suppliers/{shelf['careful']}",
        json={k: current[k] for k in ("name", "email", "phone", "address")} | {"trusted": True},
    )

    assert changed.json["trusted"] is True
