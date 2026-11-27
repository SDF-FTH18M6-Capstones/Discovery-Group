import json
from datetime import timedelta
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import Business, Category, MoneyImport, MoneyTransaction, Product
from app.whatsapp import deliver, normalise, payload, send_now, tidy
from tests.test_insights import at, ring, today
from tests.test_summary import TOKEN, sell


@pytest.fixture()
def sent(app):
    return app.extensions.setdefault("whatsapp_outbox", [])


def turn_on(admin, number="0712 345 678"):
    return admin.put(
        "/api/business/whatsapp", json={"whatsapp_number": number, "whatsapp_alerts": True}
    )


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("0712 345 678", "254712345678"),
        ("+254 712-345-678", "254712345678"),
        ("712345678", "254712345678"),
        ("0110 123 456", "254110123456"),
        ("12345", None),
        ("", None),
    ],
)
def test_numbers_are_written_the_way_whatsapp_wants(given, expected):
    assert normalise(given) == expected


def test_alert_text_is_kept_to_one_line():
    assert tidy("Sugar\nis\tlow   now") == "Sugar is low now"
    assert len(tidy("x" * 2000)) == 900


def test_settings_are_saved_and_checked(admin):
    assert admin.get("/api/business/whatsapp").json == {
        "whatsapp_number": None,
        "whatsapp_alerts": False,
        "connected": False,
    }

    saved = turn_on(admin)
    missing = admin.put("/api/business/whatsapp", json={"whatsapp_alerts": True})
    nonsense = admin.put(
        "/api/business/whatsapp", json={"whatsapp_number": "123", "whatsapp_alerts": False}
    )

    assert saved.json["whatsapp_number"] == "254712345678"
    assert missing.status_code == 422
    assert nonsense.status_code == 422


def test_a_test_message_can_be_sent(admin, sent):
    assert admin.post("/api/business/whatsapp/test").status_code == 409

    turn_on(admin)
    response = admin.post("/api/business/whatsapp/test")

    assert response.json == {"sent": True}
    assert sent[-1]["to"] == "254712345678"
    assert sent[-1]["business"] == "Test Shop"


def test_low_stock_reaches_whatsapp_once(admin, as_role, sent):
    category = Category(name="Grocery")
    db.session.add(category)
    db.session.flush()
    sugar = Product(
        sku="SUG",
        name="Sugar",
        category_id=category.id,
        cost_price=Decimal("100"),
        selling_price=Decimal("150"),
        quantity=6,
        reorder_level=5,
    )
    db.session.add(sugar)
    db.session.commit()
    turn_on(admin)
    seller = as_role("sales")

    sell(seller, sugar.id, 1)
    sell(seller, sugar.id, 1)

    alerts = [m["message"] for m in sent]
    assert alerts == ["Sugar is low on stock (5 left)."]


def test_no_alerts_unless_turned_on(admin, as_role, sent):
    category = Category(name="Grocery")
    db.session.add(category)
    db.session.flush()
    sugar = Product(
        sku="SUG",
        name="Sugar",
        category_id=category.id,
        cost_price=Decimal("100"),
        selling_price=Decimal("150"),
        quantity=6,
        reorder_level=5,
    )
    db.session.add(sugar)
    db.session.commit()

    sell(as_role("sales"), sugar.id, 2)

    assert sent == []


def test_the_evening_run_warns_about_cash(client, admin, sent):
    category = Category(name="Drinks")
    db.session.add(category)
    db.session.flush()
    tea = Product(
        sku="TEA",
        name="Tea",
        category_id=category.id,
        cost_price=Decimal("20"),
        selling_price=Decimal("50"),
        quantity=500,
    )
    db.session.add(tea)
    db.session.commit()
    for back in range(1, 30):
        ring(admin.user.id, tea, today() - timedelta(days=back))
    batch = MoneyImport(source="sms", added=0, duplicates=0, skipped=0, created_by=admin.user.id)
    batch.transactions.append(
        MoneyTransaction(
            receipt="RENT000010",
            occurred_at=at(today() - timedelta(days=3)),
            direction="out",
            amount=Decimal("20000"),
            kind="paybill",
            category="rent",
            counterparty="LANDLORD",
        )
    )
    db.session.add(batch)
    business = db.session.get(Business, admin.user.business_id)
    business.daily_summary = False
    db.session.commit()
    turn_on(admin)

    response = client.post("/api/tasks/daily-summary", headers=TOKEN)

    assert response.json == {"sent": 0}
    assert sent[-1]["message"].startswith("Cash: more is likely to go out than come in")


def test_the_message_uses_the_approved_template(app):
    body = payload(app.config, "254712345678", "Test Shop", "Sugar is low")

    assert body["to"] == "254712345678"
    assert body["template"]["name"] == "stockpilot_alert"
    assert body["template"]["components"][0]["parameters"] == [
        {"type": "text", "text": "Test Shop"},
        {"type": "text", "text": "Sugar is low"},
    ]


class Reply:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_delivery_calls_the_cloud_api(app, monkeypatch):
    seen = {}

    def fake_open(request, timeout):
        seen["url"] = request.full_url
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.data)
        return Reply()

    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    config = {**app.config, "WHATSAPP_TOKEN": "tok", "WHATSAPP_PHONE_ID": "999"}

    assert deliver(config, payload(config, "254712345678", "Shop", "Hi")) is True
    assert seen["url"] == "https://graph.facebook.com/v23.0/999/messages"
    assert seen["auth"] == "Bearer tok"
    assert seen["body"]["type"] == "template"


def test_delivery_failures_are_logged_not_raised(app, monkeypatch, caplog):
    def broken(request, timeout):
        raise TimeoutError

    monkeypatch.setattr("urllib.request.urlopen", broken)
    config = {**app.config, "WHATSAPP_TOKEN": "tok", "WHATSAPP_PHONE_ID": "999"}

    assert deliver(config, payload(config, "254712345678", "Shop", "Hi")) is False
    assert "Could not send a WhatsApp alert" in caplog.text


def test_with_keys_set_alerts_go_out_in_the_background(app, monkeypatch):
    started = []

    class Thread:
        def __init__(self, target, args, daemon):
            started.append((target, args))

        def start(self):
            pass

    monkeypatch.setattr("app.whatsapp.threading.Thread", Thread)
    app.config.update(WHATSAPP_TOKEN="tok", WHATSAPP_PHONE_ID="999")

    send_now(app, "254712345678", "Shop", "Hi")

    assert started[0][0] is deliver
    assert started[0][1][1]["to"] == "254712345678"
