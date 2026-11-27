import base64
import hashlib
import hmac
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import current_app, request

HOSTS = {"sandbox": "https://sandbox.safaricom.co.ke", "live": "https://api.safaricom.co.ke"}
MODES = ("off", "simulate", "sandbox", "live")
NAIROBI = ZoneInfo("Africa/Nairobi")
_token = {"value": None, "expires": 0.0, "key": None}


class MpesaError(Exception):
    pass


def mode():
    chosen = current_app.config["MPESA_MODE"].strip().lower()
    if chosen in MODES:
        return chosen
    return "off" if current_app.config.get("IS_PRODUCTION") else "simulate"


def normalise_phone(raw):
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("0") and len(digits) == 10:
        digits = "254" + digits[1:]
    elif len(digits) == 9 and digits[0] in "17":
        digits = "254" + digits
    if re.fullmatch(r"254[17]\d{8}", digits):
        return digits
    return None


def callback_token():
    secret = current_app.config["SECRET_KEY"].encode()
    return hmac.new(secret, b"mpesa-callback", hashlib.sha256).hexdigest()[:32]


def callback_url():
    base = current_app.config["MPESA_CALLBACK_BASE"].rstrip("/") or request.url_root.rstrip("/")
    return f"{base}/api/payments/mpesa/callback/{callback_token()}"


def _call(path, body=None, auth=None):
    url = HOSTS[mode()] + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if body is not None else "GET")
    req.add_header("Authorization", auth or f"Bearer {access_token()}")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as err:
        try:
            detail = json.loads(err.read() or b"{}")
        except ValueError:
            detail = {}
        message = detail.get("errorMessage") or detail.get("ResultDesc") or err.reason
        raise MpesaError(f"M-Pesa said: {message}") from err
    except (urllib.error.URLError, TimeoutError, ValueError) as err:
        raise MpesaError("Could not reach M-Pesa. Check the connection and try again.") from err


def access_token():
    config = current_app.config
    key = (config["MPESA_CONSUMER_KEY"], config["MPESA_CONSUMER_SECRET"], mode())
    if not key[0] or not key[1]:
        raise MpesaError("M-Pesa keys are missing. Set MPESA_CONSUMER_KEY and _SECRET.")
    if _token["key"] == key and _token["expires"] > time.time() + 60:
        return _token["value"]
    basic = base64.b64encode(f"{key[0]}:{key[1]}".encode()).decode()
    answer = _call("/oauth/v1/generate?grant_type=client_credentials", auth=f"Basic {basic}")
    _token.update(
        value=answer["access_token"],
        expires=time.time() + int(answer.get("expires_in", 3599)),
        key=key,
    )
    return _token["value"]


def _password():
    config = current_app.config
    stamp = datetime.now(NAIROBI).strftime("%Y%m%d%H%M%S")
    raw = f"{config['MPESA_SHORTCODE']}{config['MPESA_PASSKEY']}{stamp}"
    return base64.b64encode(raw.encode()).decode(), stamp


def stk_push(phone, amount, reference, description):
    config = current_app.config
    password, stamp = _password()
    answer = _call(
        "/mpesa/stkpush/v1/processrequest",
        {
            "BusinessShortCode": config["MPESA_SHORTCODE"],
            "Password": password,
            "Timestamp": stamp,
            "TransactionType": config["MPESA_TRANSACTION_TYPE"],
            "Amount": amount,
            "PartyA": phone,
            "PartyB": config["MPESA_PARTY_B"] or config["MPESA_SHORTCODE"],
            "PhoneNumber": phone,
            "CallBackURL": callback_url(),
            "AccountReference": reference[:12],
            "TransactionDesc": description[:13],
        },
    )
    if str(answer.get("ResponseCode")) != "0":
        raise MpesaError(answer.get("CustomerMessage") or "M-Pesa did not accept the request.")
    return answer["CheckoutRequestID"], answer.get("MerchantRequestID")


def stk_query(checkout_request_id):
    config = current_app.config
    password, stamp = _password()
    return _call(
        "/mpesa/stkpushquery/v1/query",
        {
            "BusinessShortCode": config["MPESA_SHORTCODE"],
            "Password": password,
            "Timestamp": stamp,
            "CheckoutRequestID": checkout_request_id,
        },
    )
