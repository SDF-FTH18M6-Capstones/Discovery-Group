import io
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app import mpesa
from app.extensions import db
from app.models import Category, MpesaPayment, Notification, Product, Sale
from app.vault import seal


@pytest.fixture()
def tea():
    category = Category(name="Drinks")
    db.session.add(category)
    db.session.flush()
    product = Product(
        sku="TEA",
        name="Tea",
        category_id=category.id,
        cost_price=Decimal("40.00"),
        selling_price=Decimal("99.50"),
        quantity=10,
        reorder_level=2,
    )
    db.session.add(product)
    db.session.commit()
    return product.id


@pytest.fixture()
def sandbox(app, business):
    business.mpesa_mode = "sandbox"
    business.mpesa_shortcode = "174379"
    business.mpesa_passkey = seal("passkey")
    business.mpesa_consumer_key = seal("key")
    business.mpesa_consumer_secret = seal("secret")
    db.session.commit()
    return business


def start(client, product_id, quantity=2, phone="0712 345 678", key="till-key-0001"):
    return client.post(
        "/api/payments/mpesa",
        json={
            "phone": phone,
            "items": [{"product_id": product_id, "quantity": quantity}],
            "idempotency_key": key,
        },
    )


def callback_body(checkout, code=0, receipt="QKT1ABC2DE"):
    body = {"CheckoutRequestID": checkout, "ResultCode": code, "ResultDesc": "Done"}
    if code == 0:
        body["CallbackMetadata"] = {
            "Item": [
                {"Name": "Amount", "Value": 199},
                {"Name": "MpesaReceiptNumber", "Value": receipt},
            ]
        }
    return {"Body": {"stkCallback": body}}


def stock(product_id):
    db.session.expire_all()
    return db.session.get(Product, product_id).quantity


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0712345678", "254712345678"),
        ("+254 712 345 678", "254712345678"),
        ("0110 123 456", "254110123456"),
        ("712345678", "254712345678"),
        ("0812345678", None),
        ("12345", None),
        ("", None),
    ],
)
def test_phone_numbers_are_normalised(raw, expected):
    assert mpesa.normalise_phone(raw) == expected


def test_the_till_learns_whether_prompts_are_on(as_role, app):
    seller = as_role("sales")

    assert seller.get("/api/payments/mpesa/config").json == {"mode": "simulate", "enabled": True}
    app.config["MPESA_MODE"] = "off"
    assert seller.get("/api/payments/mpesa/config").json == {"mode": "off", "enabled": False}
    app.config["MPESA_MODE"] = "simulate"


def test_production_keeps_prompts_off_until_chosen(app, business):
    app.config.update(MPESA_MODE="", IS_PRODUCTION=True)
    with app.app_context():
        assert mpesa.platform_mode() == "off"
        assert mpesa.business_account(business).mode == "off"
    app.config.update(MPESA_MODE="simulate", IS_PRODUCTION=False)


def test_asking_for_payment_holds_the_sale_until_it_is_paid(as_role, tea):
    response = start(as_role("sales"), tea)

    assert response.status_code == 201
    payment = response.json
    assert (payment["status"], payment["phone"], payment["amount"]) == (
        "pending",
        "254712345678",
        199,
    )
    assert payment["simulated"] is True
    assert db.session.scalar(db.select(db.func.count()).select_from(Sale)) == 0
    assert stock(tea) == 10


def test_the_same_tap_twice_sends_one_prompt(as_role, tea):
    seller = as_role("sales")

    first, second = start(seller, tea), start(seller, tea)

    assert first.json["id"] == second.json["id"]


def test_bad_numbers_and_short_stock_are_refused(as_role, tea):
    seller = as_role("sales")

    assert start(seller, tea, phone="12345").status_code == 422
    short = start(seller, tea, quantity=11, key="till-key-0002")
    assert short.status_code == 409
    assert short.json["error"]["message"] == "Not enough stock: Tea (10 left)."


def test_prompts_can_be_switched_off(as_role, tea, app):
    app.config["MPESA_MODE"] = "off"
    refused = start(as_role("sales"), tea)
    app.config["MPESA_MODE"] = "simulate"

    assert refused.status_code == 409


def test_a_paid_prompt_completes_the_sale_by_itself(as_role, tea):
    seller = as_role("sales")
    payment = start(seller, tea).json

    paid = seller.post(f"/api/payments/mpesa/{payment['id']}/simulate", json={"outcome": "paid"})

    assert paid.json["status"] == "paid"
    assert paid.json["receipt_number"].startswith("SIM")
    sale = seller.get(f"/api/sales/{paid.json['sale_id']}").json
    assert (sale["payment_method"], sale["total"], sale["status"]) == (
        "mpesa",
        "199.00",
        "completed",
    )
    assert sale["payment_reference"] == paid.json["receipt_number"]
    assert sale["attendant_id"] == seller.user.id
    assert stock(tea) == 8
    assert seller.get(f"/api/payments/mpesa/{payment['id']}").json["status"] == "paid"


def test_a_cancelled_prompt_sells_nothing(as_role, tea):
    seller = as_role("sales")
    payment = start(seller, tea).json

    cancelled = seller.post(
        f"/api/payments/mpesa/{payment['id']}/simulate", json={"outcome": "cancelled"}
    )
    again = seller.post(f"/api/payments/mpesa/{payment['id']}/simulate", json={"outcome": "paid"})

    assert cancelled.json["status"] == "cancelled"
    assert cancelled.json["result_desc"] == "The M-Pesa prompt was cancelled on the phone."
    assert again.json["status"] == "cancelled"
    assert stock(tea) == 10


def test_other_attendants_cannot_see_a_payment(as_role, tea):
    payment = start(as_role("sales"), tea).json

    assert as_role("sales").get(f"/api/payments/mpesa/{payment['id']}").status_code == 404
    assert as_role("admin").get(f"/api/payments/mpesa/{payment['id']}").status_code == 200


def test_live_prompts_go_to_safaricom(as_role, tea, sandbox, monkeypatch):
    sent = {}

    def fake_push(account, phone, amount, reference, description):
        sent.update(
            phone=phone, amount=amount, shortcode=account.shortcode, key=account.consumer_key
        )
        return "ws_CO_1", "29115-1"

    monkeypatch.setattr(mpesa, "stk_push", fake_push)

    payment = start(as_role("sales"), tea).json

    assert sent == {"phone": "254712345678", "amount": 199, "shortcode": "174379", "key": "key"}
    assert payment["simulated"] is False
    row = db.session.get(MpesaPayment, payment["id"])
    assert (row.checkout_request_id, row.merchant_request_id) == ("ws_CO_1", "29115-1")


def test_a_refused_prompt_is_explained(as_role, tea, sandbox, monkeypatch):
    def refuse(*_):
        raise mpesa.MpesaError("M-Pesa said: Invalid PhoneNumber")

    monkeypatch.setattr(mpesa, "stk_push", refuse)

    response = start(as_role("sales"), tea)

    assert response.status_code == 502
    assert response.json["error"]["message"] == "M-Pesa said: Invalid PhoneNumber"
    assert db.session.scalar(db.select(db.func.count()).select_from(MpesaPayment)) == 0


def live_payment(seller, tea, monkeypatch, checkout="ws_CO_9"):
    monkeypatch.setattr(mpesa, "stk_push", lambda *_: (checkout, "m-1"))
    return start(seller, tea).json


def test_safaricom_confirms_the_payment(as_role, tea, sandbox, monkeypatch, client, app):
    seller = as_role("sales")
    payment = live_payment(seller, tea, monkeypatch)
    with app.test_request_context():
        url = f"/api/payments/mpesa/callback/{mpesa.callback_token()}"

    first = client.post(url, json=callback_body("ws_CO_9"))
    second = client.post(url, json=callback_body("ws_CO_9"))

    assert first.json == {"ResultCode": 0, "ResultDesc": "Accepted"}
    assert second.status_code == 200
    shown = seller.get(f"/api/payments/mpesa/{payment['id']}").json
    assert (shown["status"], shown["receipt_number"]) == ("paid", "QKT1ABC2DE")
    assert db.session.scalar(db.select(db.func.count()).select_from(Sale)) == 1
    assert stock(tea) == 8


def test_callbacks_need_the_secret_address(client, tea):
    assert client.post("/api/payments/mpesa/callback/wrong", json={}).status_code == 404


def test_unknown_callbacks_are_acknowledged(client, app):
    with app.test_request_context():
        url = f"/api/payments/mpesa/callback/{mpesa.callback_token()}"

    assert client.post(url, json=callback_body("nobody")).json["ResultCode"] == 0
    assert client.post(url, data="not json").json["ResultCode"] == 0


def test_a_failed_payment_says_why(as_role, tea, sandbox, monkeypatch, client, app):
    seller = as_role("sales")
    payment = live_payment(seller, tea, monkeypatch)
    with app.test_request_context():
        url = f"/api/payments/mpesa/callback/{mpesa.callback_token()}"

    client.post(url, json=callback_body("ws_CO_9", code=1))

    shown = seller.get(f"/api/payments/mpesa/{payment['id']}").json
    assert (shown["status"], shown["result_desc"]) == (
        "failed",
        "The M-Pesa balance is too low.",
    )


def test_money_received_for_stock_now_gone_is_flagged(
    as_role, admin, tea, sandbox, monkeypatch, client, app
):
    seller = as_role("sales")
    payment = live_payment(seller, tea, monkeypatch)
    product = db.session.get(Product, tea)
    product.quantity = 1
    db.session.commit()
    with app.test_request_context():
        url = f"/api/payments/mpesa/callback/{mpesa.callback_token()}"

    client.post(url, json=callback_body("ws_CO_9"))

    shown = seller.get(f"/api/payments/mpesa/{payment['id']}").json
    assert shown["status"] == "paid"
    assert shown["sale_id"] is None
    assert (
        "QKT1ABC2DE for 199 was received, but the sale could not be completed" in shown["problem"]
    )
    notes = db.session.scalars(
        db.select(Notification.message).where(Notification.user_id == admin.user.id)
    ).all()
    assert notes == [shown["problem"]]


def age(payment_id, seconds):
    row = db.session.get(MpesaPayment, payment_id)
    row.created_at = datetime.now(UTC) - timedelta(seconds=seconds)
    db.session.commit()


def test_a_lost_callback_is_recovered_by_asking_safaricom(as_role, tea, sandbox, monkeypatch):
    seller = as_role("sales")
    payment = live_payment(seller, tea, monkeypatch)
    asked = []
    monkeypatch.setattr(
        mpesa, "stk_query", lambda _, checkout: asked.append(checkout) or {"ResultCode": "1032"}
    )

    early = seller.get(f"/api/payments/mpesa/{payment['id']}").json
    age(payment["id"], 30)
    later = seller.get(f"/api/payments/mpesa/{payment['id']}").json

    assert early["status"] == "pending"
    assert asked == ["ws_CO_9"]
    assert later["status"] == "cancelled"


def test_still_processing_keeps_waiting_then_gives_up(as_role, tea, sandbox, monkeypatch):
    seller = as_role("sales")
    payment = live_payment(seller, tea, monkeypatch)

    def busy(*_):
        raise mpesa.MpesaError("M-Pesa said: The transaction is being processed")

    monkeypatch.setattr(mpesa, "stk_query", busy)
    age(payment["id"], 30)
    waiting = seller.get(f"/api/payments/mpesa/{payment['id']}").json
    row = db.session.get(MpesaPayment, payment["id"])
    row.checked_at = None
    db.session.commit()
    age(payment["id"], 400)
    given_up = seller.get(f"/api/payments/mpesa/{payment['id']}").json

    assert waiting["status"] == "pending"
    assert (given_up["status"], given_up["result_desc"]) == (
        "failed",
        "The phone did not answer in time.",
    )


def test_a_paid_query_waits_for_the_callback(as_role, tea, sandbox, monkeypatch):
    seller = as_role("sales")
    payment = live_payment(seller, tea, monkeypatch)
    monkeypatch.setattr(mpesa, "stk_query", lambda *_: {"ResultCode": "0"})
    age(payment["id"], 30)

    assert seller.get(f"/api/payments/mpesa/{payment['id']}").json["status"] == "pending"


def test_simulation_is_only_for_test_mode(as_role, tea, sandbox, monkeypatch):
    seller = as_role("sales")
    payment = live_payment(seller, tea, monkeypatch)

    refused = seller.post(f"/api/payments/mpesa/{payment['id']}/simulate", json={"outcome": "paid"})

    assert refused.status_code == 409


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


ACCOUNT = mpesa.Account(mode="sandbox", consumer_key="k", consumer_secret="s")


def test_the_client_signs_requests_for_daraja(app, monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(req)
        if "oauth" in req.full_url:
            return FakeResponse(b'{"access_token": "tok", "expires_in": "3599"}')
        return FakeResponse(
            b'{"ResponseCode": "0", "CheckoutRequestID": "ws_1", "MerchantRequestID": "m_1"}'
        )

    monkeypatch.setattr(mpesa.urllib.request, "urlopen", fake_urlopen)
    mpesa._tokens.clear()
    with app.test_request_context(base_url="https://api.example.com"):
        answer = mpesa.stk_push(ACCOUNT, "254712345678", 199, "Demo Shop Ltd", "StockPilot sale")
        mpesa.stk_query(ACCOUNT, "ws_1")

    assert answer == ("ws_1", "m_1")
    assert calls[0].full_url.startswith("https://sandbox.safaricom.co.ke/oauth/v1/generate")
    assert calls[0].get_header("Authorization") == "Basic azpz"
    push = json.loads(calls[1].data)
    assert calls[1].get_header("Authorization") == "Bearer tok"
    assert (push["Amount"], push["PartyA"], push["PartyB"], push["AccountReference"]) == (
        199,
        "254712345678",
        "174379",
        "Demo Shop Lt",
    )
    assert push["CallBackURL"].startswith("https://api.example.com/api/payments/mpesa/callback/")
    assert len(calls) == 3


def test_daraja_errors_become_plain_messages(app, monkeypatch):
    def broken(req, timeout):
        raise mpesa.urllib.error.HTTPError(
            req.full_url, 400, "Bad Request", {}, io.BytesIO(b'{"errorMessage": "Invalid Amount"}')
        )

    monkeypatch.setattr(mpesa.urllib.request, "urlopen", broken)
    mpesa._tokens[("sandbox", "k", "s")] = ("tok", 9e18)
    try:
        with app.test_request_context(), pytest.raises(mpesa.MpesaError) as error:
            mpesa.stk_push(ACCOUNT, "254712345678", 1, "Shop", "Sale")
        monkeypatch.setattr(
            mpesa.urllib.request,
            "urlopen",
            lambda *_a, **_k: (_ for _ in ()).throw(mpesa.urllib.error.URLError("down")),
        )
        with app.test_request_context(), pytest.raises(mpesa.MpesaError) as offline:
            mpesa.stk_query(ACCOUNT, "ws_1")
        with app.test_request_context(), pytest.raises(mpesa.MpesaError) as no_keys:
            mpesa.access_token(mpesa.Account(mode="sandbox"))
    finally:
        mpesa._tokens.clear()

    assert str(error.value) == "M-Pesa said: Invalid Amount"
    assert str(offline.value) == "Could not reach M-Pesa. Check the connection and try again."
    assert "consumer key and secret are missing" in str(no_keys.value)
