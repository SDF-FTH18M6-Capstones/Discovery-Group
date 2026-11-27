from datetime import date, timedelta
from decimal import Decimal

import pytest

from app import mpesa
from app.billing import add_months, business_today
from app.extensions import db
from app.models import Category, MpesaPayment, Notification, Product


@pytest.fixture()
def lapsed(app, business):
    app.config["SUBSCRIPTIONS_REQUIRED"] = True
    business.trial_ends_on = business_today(business) - timedelta(days=30)
    db.session.commit()
    yield business
    app.config["SUBSCRIPTIONS_REQUIRED"] = False


def pay(client, months=3, phone="0712345678"):
    return client.post("/api/billing/pay", json={"months": months, "phone": phone})


@pytest.mark.parametrize(
    ("start", "months", "expected"),
    [
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2028, 1, 31), 1, date(2028, 2, 29)),
        (date(2026, 11, 15), 3, date(2027, 2, 15)),
        (date(2026, 12, 1), 12, date(2027, 12, 1)),
    ],
)
def test_months_are_added_like_a_calendar(start, months, expected):
    assert add_months(start, months) == expected


def test_a_new_business_starts_on_a_free_trial(client):
    response = client.post(
        "/api/auth/register-business",
        json={
            "business_name": "Mama Mboga",
            "full_name": "Wanjiku Kamau",
            "email": "w@mboga.test",
            "password": "Secret123!",
        },
    )

    subscription = response.json["user"]["business"]["subscription"]
    assert subscription["status"] == "trial"
    assert subscription["days_left"] == 14
    assert subscription["read_only"] is False


def test_the_admin_sees_the_plan_and_price(admin, business):
    business.trial_ends_on = business_today(business) + timedelta(days=5)
    db.session.commit()

    overview = admin.get("/api/billing").json

    assert overview["status"] == "trial"
    assert overview["days_left"] == 5
    assert overview["price"] == 1500
    assert overview["plans"] == [1, 3, 6, 12]
    assert overview["online_payment"] is True
    assert overview["payments"] == []


def test_paying_extends_from_the_end_of_the_trial(admin, business, outbox):
    trial_end = business_today(business) + timedelta(days=5)
    business.trial_ends_on = trial_end
    db.session.commit()

    started = pay(admin).json
    paid = admin.post(
        f"/api/billing/payments/{started['id']}/simulate", json={"outcome": "paid"}
    ).json

    assert (started["amount"], started["months"], started["purpose"]) == (4500, 3, "subscription")
    assert paid["status"] == "paid"
    overview = admin.get("/api/billing").json
    assert overview["status"] == "active"
    assert overview["paid_until"] == add_months(trial_end, 3).isoformat()
    assert [p["receipt_number"] for p in overview["payments"]] == [paid["receipt_number"]]
    assert outbox[-1]["subject"] == "StockPilot subscription receipt"
    assert f"paid until {add_months(trial_end, 3):%d %B %Y}" in outbox[-1]["body"]


def test_paying_after_it_ran_out_starts_today(admin, lapsed):
    started = pay(admin, months=1).json
    admin.post(f"/api/billing/payments/{started['id']}/simulate", json={"outcome": "paid"})

    expected = add_months(business_today(lapsed), 1)
    assert admin.get("/api/billing").json["paid_until"] == expected.isoformat()


def test_a_cancelled_payment_changes_nothing(admin):
    started = pay(admin).json

    cancelled = admin.post(
        f"/api/billing/payments/{started['id']}/simulate", json={"outcome": "cancelled"}
    ).json

    assert cancelled["status"] == "cancelled"
    assert admin.get("/api/billing").json["paid_until"] is None


def test_odd_plans_and_numbers_are_refused(admin):
    assert pay(admin, months=2).status_code == 422
    assert pay(admin, phone="123").status_code == 422


def test_paying_online_can_be_unavailable(admin, app):
    app.config["MPESA_MODE"] = "off"
    refused = pay(admin)
    app.config["MPESA_MODE"] = "simulate"

    assert refused.status_code == 409
    assert "Contact StockPilot" in refused.json["error"]["message"]


def test_subscriptions_go_to_stockpilots_own_paybill(admin, app, monkeypatch):
    app.config.update(
        MPESA_MODE="sandbox",
        MPESA_CONSUMER_KEY="platform-key",
        MPESA_CONSUMER_SECRET="platform-secret",
        MPESA_SHORTCODE="600100",
    )
    used = {}

    def fake_push(account, phone, amount, reference, description):
        used.update(shortcode=account.shortcode, key=account.consumer_key, reference=reference)
        return "ws_SUB_1", "m-1"

    monkeypatch.setattr(mpesa, "stk_push", fake_push)
    try:
        started = pay(admin, months=1)
    finally:
        app.config.update(
            MPESA_MODE="simulate",
            MPESA_CONSUMER_KEY="",
            MPESA_CONSUMER_SECRET="",
            MPESA_SHORTCODE="174379",
        )

    assert started.json["simulated"] is False
    assert used == {
        "shortcode": "600100",
        "key": "platform-key",
        "reference": f"SP{admin.user.business_id}",
    }


def test_safaricom_confirms_a_subscription_payment(admin, app, monkeypatch, client):
    app.config.update(MPESA_MODE="sandbox", MPESA_CONSUMER_KEY="k", MPESA_CONSUMER_SECRET="s")
    monkeypatch.setattr(mpesa, "stk_push", lambda *_: ("ws_SUB_2", "m-2"))
    try:
        started = pay(admin, months=1).json
        with app.test_request_context():
            url = f"/api/payments/mpesa/callback/{mpesa.callback_token()}"
        client.post(
            url,
            json={
                "Body": {
                    "stkCallback": {
                        "CheckoutRequestID": "ws_SUB_2",
                        "ResultCode": 0,
                        "CallbackMetadata": {
                            "Item": [{"Name": "MpesaReceiptNumber", "Value": "QSUB123"}]
                        },
                    }
                }
            },
        )
    finally:
        app.config.update(MPESA_MODE="simulate", MPESA_CONSUMER_KEY="", MPESA_CONSUMER_SECRET="")

    shown = admin.get(f"/api/billing/payments/{started['id']}").json
    assert (shown["status"], shown["receipt_number"]) == ("paid", "QSUB123")
    notes = db.session.scalars(
        db.select(Notification.message).where(Notification.user_id == admin.user.id)
    ).all()
    assert any("QSUB123" in note for note in notes)


def test_sale_and_subscription_payments_stay_apart(admin, as_role):
    started = pay(admin).json

    assert as_role("sales").get(f"/api/payments/mpesa/{started['id']}").status_code == 404
    assert admin.get(f"/api/payments/mpesa/{started['id']}").status_code == 404


def test_a_lapsed_business_can_read_but_not_change(admin, as_role, lapsed):
    seller = as_role("sales")
    category = Category(name="Drinks")
    db.session.add(category)
    db.session.flush()
    db.session.add(
        Product(
            sku="T",
            name="Tea",
            category_id=category.id,
            cost_price=Decimal("1"),
            selling_price=Decimal("2"),
            quantity=5,
        )
    )
    db.session.commit()

    blocked = seller.post(
        "/api/sales/", json={"payment_method": "cash", "items": [{"product_id": 1, "quantity": 1}]}
    )

    assert blocked.status_code == 403
    assert blocked.json["error"]["reason"] == "subscription_ended"
    assert seller.get("/api/products/").status_code == 200
    assert seller.post("/api/notifications/read-all").status_code == 200
    assert admin.get("/api/auth/me").json["business"]["subscription"]["read_only"] is True
    assert pay(admin).status_code == 201


def test_the_grace_week_keeps_everything_open(admin, lapsed):
    lapsed.trial_ends_on = business_today(lapsed) - timedelta(days=3)
    db.session.commit()

    subscription = admin.get("/api/auth/me").json["business"]["subscription"]

    assert (subscription["status"], subscription["read_only"]) == ("grace", False)
    assert (
        admin.put("/api/business/mpesa", json={"mode": "off", "type": "paybill"}).status_code == 200
    )


def test_nothing_locks_when_subscriptions_are_not_required(admin, business):
    business.trial_ends_on = business_today(business) - timedelta(days=60)
    db.session.commit()

    subscription = admin.get("/api/auth/me").json["business"]["subscription"]

    assert (subscription["status"], subscription["read_only"]) == ("expired", False)


def test_subscription_payments_are_kept_per_business(admin):
    pay(admin)

    assert db.session.scalar(db.select(MpesaPayment.business_id)) == admin.user.business_id
