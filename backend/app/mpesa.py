import base64
import hashlib
import hmac
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import current_app, request

from app.vault import unseal

HOSTS = {"sandbox": "https://sandbox.safaricom.co.ke", "live": "https://api.safaricom.co.ke"}
MODES = ("off", "simulate", "sandbox", "live")
SANDBOX_SHORTCODE = "174379"
SANDBOX_PASSKEY = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"
NAIROBI = ZoneInfo("Africa/Nairobi")
_tokens = {}


class MpesaError(Exception):
    pass


@dataclass(frozen=True)
class Account:
    mode: str
    consumer_key: str = ""
    consumer_secret: str = ""
    shortcode: str = SANDBOX_SHORTCODE
    passkey: str = SANDBOX_PASSKEY
    transaction_type: str = "CustomerPayBillOnline"
    party_b: str = ""

    @property
    def online(self):
        return self.mode in ("sandbox", "live")


def platform_mode():
    chosen = current_app.config["MPESA_MODE"].strip().lower()
    if chosen in MODES:
        return chosen
    return "off" if current_app.config.get("IS_PRODUCTION") else "simulate"


def platform_account():
    config = current_app.config
    return Account(
        mode=platform_mode(),
        consumer_key=config["MPESA_CONSUMER_KEY"],
        consumer_secret=config["MPESA_CONSUMER_SECRET"],
        shortcode=config["MPESA_SHORTCODE"],
        passkey=config["MPESA_PASSKEY"],
        transaction_type=config["MPESA_TRANSACTION_TYPE"],
        party_b=config["MPESA_PARTY_B"],
    )


def business_account(business):
    mode = business.mpesa_mode or ("simulate" if platform_mode() == "simulate" else "off")
    if mode not in ("sandbox", "live"):
        return Account(mode=mode)
    till = business.mpesa_type == "till"
    return Account(
        mode=mode,
        consumer_key=unseal(business.mpesa_consumer_key),
        consumer_secret=unseal(business.mpesa_consumer_secret),
        shortcode=business.mpesa_shortcode or "",
        passkey=unseal(business.mpesa_passkey),
        transaction_type="CustomerBuyGoodsOnline" if till else "CustomerPayBillOnline",
        party_b=(business.mpesa_till or "") if till else "",
    )


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


def _call(account, path, body=None, auth=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        HOSTS[account.mode] + path, data=data, method="POST" if body is not None else "GET"
    )
    req.add_header("Authorization", auth or f"Bearer {access_token(account)}")
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


def access_token(account):
    if not account.consumer_key or not account.consumer_secret:
        raise MpesaError("The M-Pesa consumer key and secret are missing.")
    cache_key = (account.mode, account.consumer_key, account.consumer_secret)
    cached = _tokens.get(cache_key)
    if cached and cached[1] > time.time() + 60:
        return cached[0]
    basic = base64.b64encode(f"{account.consumer_key}:{account.consumer_secret}".encode()).decode()
    answer = _call(
        account, "/oauth/v1/generate?grant_type=client_credentials", auth=f"Basic {basic}"
    )
    _tokens[cache_key] = (
        answer["access_token"],
        time.time() + int(answer.get("expires_in", 3599)),
    )
    return answer["access_token"]


def _password(account):
    stamp = datetime.now(NAIROBI).strftime("%Y%m%d%H%M%S")
    raw = f"{account.shortcode}{account.passkey}{stamp}"
    return base64.b64encode(raw.encode()).decode(), stamp


def stk_push(account, phone, amount, reference, description):
    password, stamp = _password(account)
    answer = _call(
        account,
        "/mpesa/stkpush/v1/processrequest",
        {
            "BusinessShortCode": account.shortcode,
            "Password": password,
            "Timestamp": stamp,
            "TransactionType": account.transaction_type,
            "Amount": amount,
            "PartyA": phone,
            "PartyB": account.party_b or account.shortcode,
            "PhoneNumber": phone,
            "CallBackURL": callback_url(),
            "AccountReference": reference[:12],
            "TransactionDesc": description[:13],
        },
    )
    if str(answer.get("ResponseCode")) != "0":
        raise MpesaError(answer.get("CustomerMessage") or "M-Pesa did not accept the request.")
    return answer["CheckoutRequestID"], answer.get("MerchantRequestID")


def stk_query(account, checkout_request_id):
    password, stamp = _password(account)
    return _call(
        account,
        "/mpesa/stkpushquery/v1/query",
        {
            "BusinessShortCode": account.shortcode,
            "Password": password,
            "Timestamp": stamp,
            "CheckoutRequestID": checkout_request_id,
        },
    )
