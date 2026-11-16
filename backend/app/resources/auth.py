import re
import secrets
from datetime import UTC, datetime, timedelta

from flask import current_app
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    current_user,
    jwt_required,
)
from flask_smorest import Blueprint, abort
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate, validates

from app.auth import roles_required
from app.email import send_email
from app.extensions import db
from app.models import Employee, User
from app.models.user import check_secret, hash_secret

blp = Blueprint("auth", __name__, url_prefix="/api/auth", description="Sign-in and accounts")

BAD_LOGIN = "Email or password is incorrect."
BAD_CODE = "The code is wrong or has expired. Sign in again to get a new code."


# ---------- schemas ----------


class RegisterSchema(Schema):
    class Meta:
        unknown = EXCLUDE  # a "role" sent by the browser is ignored, never trusted

    full_name = fields.String(required=True, validate=validate.Length(min=2, max=120))
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)

    @validates("password")
    def strong_enough(self, value, **kwargs):
        if len(value) < 8 or not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise ValidationError("Use at least 8 characters with letters and numbers.")
        if len(value.encode("utf-8")) > 72:
            raise ValidationError("Use at most 72 characters.")


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)


class OtpSchema(Schema):
    email = fields.Email(required=True)
    code = fields.String(
        required=True, validate=validate.Regexp(r"^\d{6}$", error="Enter the 6-digit code.")
    )


class TokenSchema(Schema):
    token = fields.String(required=True, validate=validate.Length(min=1))


class EmailOnlySchema(Schema):
    email = fields.Email(required=True)


class AccountSchema(Schema):
    id = fields.Integer()
    full_name = fields.String()
    email = fields.String()
    role = fields.String()
    is_verified = fields.Boolean()


class MessageSchema(Schema):
    message = fields.String()
    dev_code = fields.String()


class SessionSchema(Schema):
    access_token = fields.String()
    refresh_token = fields.String()
    user = fields.Nested(AccountSchema)


class AccessSchema(Schema):
    access_token = fields.String()


# ---------- helpers ----------


def serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="verify-email")


_dummy = {}


def dummy_hash():
    """A real hash to check against when the email is unknown, so the answer takes as long
    as for a real account and nobody can tell which emails exist."""
    if "hash" not in _dummy:
        _dummy["hash"] = hash_secret("not-a-real-password-1")
    return _dummy["hash"]


def find_user(email):
    return db.session.scalar(db.select(User).filter_by(email=email.lower()))


def send_verification(user):
    token = serializer().dumps(user.email)
    link = f"{current_app.config['FRONTEND_URL']}/verify-email?token={token}"
    send_email(
        user.email,
        "Verify your StockPilot account",
        f"Hello {user.full_name},\n\nConfirm your email to activate your account:\n{link}\n\n"
        f"The link expires in {current_app.config['EMAIL_TOKEN_HOURS']} hours.",
    )


# ---------- routes ----------


@blp.route("/register", methods=["POST"])
@blp.arguments(RegisterSchema)
@blp.response(201, MessageSchema)
@blp.doc(security=[])
def register(data):
    """Create an account. Every new account is an Employee, whatever the request says."""
    if find_user(data["email"]):
        abort(409, message="An account with this email already exists.")
    user = Employee(full_name=data["full_name"], email=data["email"].lower(), is_verified=False)
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    send_verification(user)
    return {"message": "Account created. Check your email for the verification link."}


@blp.route("/verify-email", methods=["POST"])
@blp.arguments(TokenSchema)
@blp.response(200, MessageSchema)
@blp.doc(security=[])
def verify_email(data):
    """Confirm the email address with the token from the verification link."""
    max_age = current_app.config["EMAIL_TOKEN_HOURS"] * 3600
    try:
        email = serializer().loads(data["token"], max_age=max_age)
    except SignatureExpired:
        abort(400, message="This link has expired. Ask for a new one.")
    except BadSignature:
        abort(400, message="This link is not valid.")
    user = find_user(email)
    if user is None:
        abort(400, message="This link is not valid.")
    user.is_verified = True
    db.session.commit()
    return {"message": "Email verified. You can now sign in."}


@blp.route("/resend-verification", methods=["POST"])
@blp.arguments(EmailOnlySchema)
@blp.response(200, MessageSchema)
@blp.doc(security=[])
def resend_verification(data):
    """Send the verification link again. Always answers the same, so nobody can probe emails."""
    user = find_user(data["email"])
    if user and not user.is_verified:
        send_verification(user)
    return {"message": "If that account exists and is not verified, we sent a new link."}


@blp.route("/login", methods=["POST"])
@blp.arguments(LoginSchema)
@blp.response(200, MessageSchema)
@blp.doc(security=[])
def login(data):
    """Step 1: check email and password, then email a 6-digit code."""
    user = find_user(data["email"])
    if user is None:
        check_secret(dummy_hash(), data["password"])  # same delay as a real check
        abort(401, message=BAD_LOGIN)
    if not user.check_password(data["password"]):
        abort(401, message=BAD_LOGIN)
    if not user.is_verified:
        abort(403, message="Verify your email before signing in.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    user.otp_hash = hash_secret(code)
    user.otp_expires_at = datetime.now(UTC) + timedelta(minutes=current_app.config["OTP_MINUTES"])
    user.otp_attempts = 0
    db.session.commit()
    send_email(
        user.email,
        "Your StockPilot sign-in code",
        f"Your code is {code}. It expires in {current_app.config['OTP_MINUTES']} minutes.",
    )
    body = {"message": "We sent a 6-digit code to your email."}
    if current_app.config["DEV_SHOW_OTP"]:
        body["dev_code"] = code
    return body


@blp.route("/verify-otp", methods=["POST"])
@blp.arguments(OtpSchema)
@blp.response(200, SessionSchema)
@blp.doc(security=[])
def verify_otp(data):
    """Step 2: check the emailed code and return the tokens."""
    user = find_user(data["email"])
    if user is None or user.otp_hash is None:
        abort(401, message=BAD_CODE)

    expired = user.otp_expires_at is None or user.otp_expires_at < datetime.now(UTC)
    too_many = user.otp_attempts >= current_app.config["OTP_MAX_ATTEMPTS"]
    if expired or too_many:
        user.otp_hash = None
        db.session.commit()
        abort(401, message=BAD_CODE)

    if not check_secret(user.otp_hash, data["code"]):
        user.otp_attempts += 1
        db.session.commit()
        abort(401, message=BAD_CODE)

    user.otp_hash = None  # a code works once
    user.otp_expires_at = None
    user.otp_attempts = 0
    db.session.commit()
    return {
        "access_token": create_access_token(identity=user, additional_claims={"role": user.role}),
        "refresh_token": create_refresh_token(identity=user),
        "user": user,
    }


@blp.route("/refresh", methods=["POST"])
@blp.response(200, AccessSchema)
@jwt_required(refresh=True)
def refresh():
    """Swap the refresh token for a new access token."""
    token = create_access_token(
        identity=current_user, additional_claims={"role": current_user.role}
    )
    return {"access_token": token}


@blp.route("/me")
@blp.response(200, AccountSchema)
@roles_required()
def me():
    """The signed-in user."""
    return current_user