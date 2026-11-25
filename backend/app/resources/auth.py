import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

from flask import current_app
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    current_user,
    decode_token,
    get_jwt,
    jwt_required,
)
from flask_smorest import Blueprint, abort
from marshmallow import EXCLUDE, ValidationError, fields, validate, validates

from app.audit import audit
from app.auth import roles_required
from app.extensions import db, limiter
from app.mail import queue_email
from app.models import Admin, Business, Employee, PasswordReset, RevokedToken, User
from app.models.user import check_secret, hash_secret
from app.schemas import Schema
from app.tenancy import tenant

blp = Blueprint("auth", __name__, url_prefix="/api/auth", description="Sign-in and accounts")

BAD_LOGIN = "Email or password is incorrect."
RESET_SENT = "If that email has an account, we sent a link to reset the password."
RESET_HOURS = 1


def check_strength(value):
    if len(value) < 8 or not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValidationError("Use at least 8 characters with letters and numbers.")
    if len(value.encode("utf-8")) > 72:
        raise ValidationError("Use at most 72 characters.")


class RegisterSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    full_name = fields.String(required=True, validate=validate.Length(min=2, max=120))
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)
    join_code = fields.String(required=True, validate=validate.Length(min=4, max=12))

    @validates("password")
    def strong_enough(self, value, **kwargs):
        check_strength(value)


class RegisterBusinessSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    business_name = fields.String(required=True, validate=validate.Length(min=2, max=150))
    full_name = fields.String(required=True, validate=validate.Length(min=2, max=120))
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)

    @validates("password")
    def strong_enough(self, value, **kwargs):
        check_strength(value)


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)


class BusinessBrief(Schema):
    id = fields.Integer()
    name = fields.String()
    currency = fields.String()
    timezone = fields.String()
    vat_rate = fields.Decimal(places=2, as_string=True)


class AccountSchema(Schema):
    id = fields.Integer()
    full_name = fields.String()
    email = fields.String()
    phone = fields.String(allow_none=True)
    role = fields.String()
    business = fields.Nested(BusinessBrief)


class MessageSchema(Schema):
    message = fields.String()


class SessionSchema(Schema):
    access_token = fields.String()
    refresh_token = fields.String()
    user = fields.Nested(AccountSchema)


class ProfileSchema(Schema):
    full_name = fields.String(required=True, validate=validate.Length(min=2, max=120))
    phone = fields.String(
        allow_none=True,
        load_default=None,
        validate=validate.Regexp(r"^\+?[0-9 ]{7,20}$", error="Enter a valid phone number."),
    )


class PasswordSchema(Schema):
    current_password = fields.String(required=True, load_only=True)
    new_password = fields.String(required=True, load_only=True)

    @validates("new_password")
    def strong_enough(self, value, **kwargs):
        check_strength(value)


class ForgotSchema(Schema):
    email = fields.Email(required=True)


class ResetSchema(Schema):
    token = fields.String(required=True, validate=validate.Length(min=10, max=200))
    password = fields.String(required=True, load_only=True)

    @validates("password")
    def strong_enough(self, value, **kwargs):
        check_strength(value)


class AccessSchema(Schema):
    access_token = fields.String()


_dummy = {}


def dummy_hash():
    if "hash" not in _dummy:
        _dummy["hash"] = hash_secret("not-a-real-password-1")
    return _dummy["hash"]


def find_user(email):
    return db.session.scalar(db.select(User).filter_by(email=email.lower()))


TOO_MANY = "Too many attempts. Wait a minute and try again."


def rate_limit():
    return current_app.config["LOGIN_RATE_LIMIT"]


def start_session(user):
    refresh = create_refresh_token(identity=user, additional_claims={"sv": user.session_version})
    session_id = decode_token(refresh)["jti"]
    access = create_access_token(
        identity=user,
        additional_claims={"role": user.role, "sid": session_id, "sv": user.session_version},
    )
    return {"access_token": access, "refresh_token": refresh, "user": user}


@blp.route("/register-business", methods=["POST"])
@limiter.limit(rate_limit, error_message=TOO_MANY)
@blp.arguments(RegisterBusinessSchema)
@blp.response(201, SessionSchema)
@blp.doc(security=[])
def register_business(data):
    if find_user(data["email"]):
        abort(409, message="An account with this email already exists.")
    business = Business(name=data["business_name"])
    db.session.add(business)
    db.session.flush()
    with tenant(business.id):
        owner = Admin(full_name=data["full_name"], email=data["email"].lower())
        owner.set_password(data["password"])
        db.session.add(owner)
        db.session.flush()
        audit(
            "created",
            "business",
            business.id,
            f"Business {business.name} created",
            user_id=owner.id,
        )
        db.session.commit()
    return start_session(owner)


@blp.route("/register", methods=["POST"])
@limiter.limit(rate_limit, error_message=TOO_MANY)
@blp.arguments(RegisterSchema)
@blp.response(201, MessageSchema)
@blp.doc(security=[])
def register(data):
    business = db.session.scalar(
        db.select(Business).filter_by(join_code=data["join_code"].upper(), is_active=True)
    )
    if business is None:
        abort(
            422,
            message="Some fields are invalid.",
            messages={"json": {"join_code": ["This join code is not valid. Ask your manager."]}},
        )
    if find_user(data["email"]):
        abort(409, message="An account with this email already exists.")
    with tenant(business.id):
        user = Employee(full_name=data["full_name"], email=data["email"].lower())
        user.set_password(data["password"])
        db.session.add(user)
        db.session.flush()
        audit("joined", "user", user.id, f"{user.full_name} joined", user_id=user.id)
        db.session.commit()
    return {"message": f"Account created at {business.name}. You can now sign in."}


@blp.route("/login", methods=["POST"])
@limiter.limit(rate_limit, error_message=TOO_MANY)
@blp.arguments(LoginSchema)
@blp.response(200, SessionSchema)
@blp.doc(security=[])
def login(data):
    user = find_user(data["email"])
    if user is None:
        check_secret(dummy_hash(), data["password"])
        abort(401, message=BAD_LOGIN)
    if not user.check_password(data["password"]):
        abort(401, message=BAD_LOGIN)
    if not user.is_active:
        abort(403, message="This account has been deactivated. Ask your administrator.")
    if not user.business.is_active:
        abort(403, message="This business is suspended. Contact StockPilot support.")
    return start_session(user)


@blp.route("/refresh", methods=["POST"])
@blp.response(200, AccessSchema)
@jwt_required(refresh=True)
def refresh():
    token = create_access_token(
        identity=current_user,
        additional_claims={
            "role": current_user.role,
            "sid": get_jwt()["jti"],
            "sv": current_user.session_version,
        },
    )
    return {"access_token": token}


@blp.route("/logout", methods=["POST"])
@blp.response(200, MessageSchema)
@jwt_required(verify_type=False)
def logout():
    claims = get_jwt()
    session_id = claims.get("sid") if claims.get("type") == "access" else claims["jti"]
    session_id = session_id or claims["jti"]
    expires = datetime.now(UTC) + current_app.config["JWT_REFRESH_TOKEN_EXPIRES"]
    for jti in {session_id, claims["jti"]}:
        if db.session.get(RevokedToken, jti) is None:
            db.session.add(RevokedToken(jti=jti, expires_at=expires))
    db.session.execute(db.delete(RevokedToken).where(RevokedToken.expires_at < datetime.now(UTC)))
    db.session.commit()
    return {"message": "Signed out."}


@blp.route("/me")
@blp.response(200, AccountSchema)
@roles_required()
def me():
    return current_user


@blp.route("/me", methods=["PUT"])
@blp.arguments(ProfileSchema)
@blp.response(200, AccountSchema)
@roles_required()
def update_me(data):
    current_user.full_name = data["full_name"]
    current_user.phone = data["phone"] or None
    db.session.commit()
    return current_user


@blp.route("/password", methods=["POST"])
@blp.arguments(PasswordSchema)
@blp.response(200, MessageSchema)
@roles_required()
def change_password(data):
    if not current_user.check_password(data["current_password"]):
        abort(
            422,
            message="Some fields are invalid.",
            messages={"json": {"current_password": ["Your current password is not correct."]}},
        )
    current_user.set_password(data["new_password"])
    db.session.commit()
    return {"message": "Password changed."}


def token_hash(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


@blp.route("/forgot-password", methods=["POST"])
@limiter.limit(rate_limit, error_message=TOO_MANY)
@blp.arguments(ForgotSchema)
@blp.response(200, MessageSchema)
@blp.doc(security=[])
def forgot_password(data):
    user = find_user(data["email"])
    if user is not None and user.is_active:
        raw = secrets.token_urlsafe(32)
        db.session.add(
            PasswordReset(
                user_id=user.id,
                token_hash=token_hash(raw),
                expires_at=datetime.now(UTC) + timedelta(hours=RESET_HOURS),
            )
        )
        link = f"{current_app.config['FRONTEND_URL']}/reset-password?token={raw}"
        queue_email(
            user.email,
            "Reset your StockPilot password",
            f"Hello {user.full_name},\n\nSomeone asked to reset your StockPilot password. "
            f"Open this link within {RESET_HOURS} hour to choose a new one:\n\n{link}\n\n"
            "If it was not you, ignore this email; your password stays the same.\n\n— StockPilot",
        )
        db.session.commit()
    return {"message": RESET_SENT}


@blp.route("/reset-password", methods=["POST"])
@limiter.limit(rate_limit, error_message=TOO_MANY)
@blp.arguments(ResetSchema)
@blp.response(200, MessageSchema)
@blp.doc(security=[])
def reset_password(data):
    reset = db.session.scalar(
        db.select(PasswordReset).filter_by(token_hash=token_hash(data["token"])).with_for_update()
    )
    now = datetime.now(UTC)
    if reset is None or reset.used_at is not None or reset.expires_at < now:
        abort(400, message="This reset link has expired or was already used. Ask for a new one.")
    user = db.session.get(User, reset.user_id)
    user.set_password(data["password"])
    user.session_version += 1
    reset.used_at = now
    db.session.commit()
    return {"message": "Password changed. You can now sign in."}
