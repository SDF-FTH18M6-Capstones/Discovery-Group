import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


def _fernet():
    secret = current_app.config["DATA_KEY"] or current_app.config["SECRET_KEY"]
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def seal(value):
    if not value:
        return None
    return _fernet().encrypt(value.encode()).decode()


def unseal(token):
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return ""
