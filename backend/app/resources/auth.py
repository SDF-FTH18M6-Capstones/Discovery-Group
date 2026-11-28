import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

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

from app import verification as verify
from app.audit import audit
from app.auth import covers_for, roles_required
from app.billing import TRIAL_DAYS, subscription
from app.extensions import db, limiter
from app.mail import queue_email
from app.models import (
    Admin,
    Business,
    Employee,
    LoginChallenge,
    PasswordReset,
    RevokedToken,
    User,
)
from app.models.user import check_secret, hash_secret
from app.notify import notify_roles
from app.resources.platform import is_platform_owner
from app.schemas import Schema
from app.shoptime import DEFAULT_ZONE
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


class SubscriptionBrief(Schema):
    status = fields.String()
    ends_on = fields.Date()
    grace_until = fields.Date()
    days_left = fields.Integer()
    read_only = fields.Boolean()
    required = fields.Boolean()


class BusinessBrief(Schema):
    id = fields.Integer()
    name = fields.String()
    currency = fields.String()
    timezone = fields.String()
    vat_rate = fields.Decimal(places=2, as_string=True)
    subscription = fields.Method("get_subscription")

    def get_subscription(self, business):
        return SubscriptionBrief().dump(subscription(business))


class AccountSchema(Schema):
    id = fields.Integer()
    full_name = fields.String()
    email = fields.String()
    email_verified = fields.Boolean()
    phone = fields.String(allow_none=True)
    role = fields.String()
    covers = fields.Function(covers_for)
    platform_owner = fields.Function(is_platform_owner)
    business = fields.Nested(BusinessBrief)


class MessageSchema(Schema):
    message = fields.String()


class SessionSchema(Schema):
    access_token = fields.String()
    refresh_token = fields.String()
    user = fields.Nested(AccountSchema)


class LoginOut(SessionSchema):
    code_required = fields.Boolean()
    challenge_id = fields.String()
    email_hint = fields.String()
    expires_in = fields.Integer()
    resend_after = fields.Integer()


class SignUpOut(SessionSchema):
    message = fields.String()
    verification_required = fields.Boolean()


class CodeIn(Schema):
    challenge_id = fields.String(required=True, validate=validate.Length(min=8, max=64))
    code = fields.String(
        required=True,
        validate=validate.Regexp(r"^\d{6}$", error="Enter the 6-digit code from the email."),
    )


class ChallengeIn(Schema):
    challenge_id = fields.String(required=True, validate=validate.Length(min=8, max=64))


class TokenIn(Schema):
    token = fields.String(required=True, validate=validate.Length(min=10, max=200))


class EmailIn(Schema):
    email = fields.Email(required=True)


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
@blp.response(201, SignUpOut)
@blp.doc(security=[])
def register_business(data):
    if find_user(data["email"]):
        abort(409, message="An account with this email already exists.")
    today = datetime.now(ZoneInfo(DEFAULT_ZONE)).date()
    business = Business(
        name=data["business_name"],
        timezone=DEFAULT_ZONE,
        trial_ends_on=today + timedelta(days=TRIAL_DAYS),
    )
    db.session.add(business)
    db.session.flush()
    with tenant(business.id):
        owner = Admin(
            full_name=data["full_name"], email=data["email"].lower(), approved_at=verify.now()
        )
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
        if verify.verification_required():
            verify.send_verification(owner)
            db.session.commit()
            return {
                "verification_required": True,
                "message": f"{business.name} is ready. We sent a link to {owner.email}: "
                "open it to confirm your email, then sign in.",
            }
        owner.email_verified_at = verify.now()
        db.session.commit()
    return {**start_session(owner), "verification_required": False}


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
        needs_approval = current_app.config["STAFF_APPROVAL_REQUIRED"]
        user = Employee(
            full_name=data["full_name"],
            email=data["email"].lower(),
            approved_at=None if needs_approval else verify.now(),
        )
        user.set_password(data["password"])
        db.session.add(user)
        db.session.flush()
        audit("joined", "user", user.id, f"{user.full_name} joined", user_id=user.id)
        if needs_approval:
            notify_roles(
                ("admin",),
                f"{user.full_name} ({user.email}) joined {business.name} and is waiting for "
                "you to approve them and choose their role.",
                link="/users?pending=true",
                email_subject=f"{user.full_name} is waiting for approval",
            )
        steps = []
        if verify.verification_required():
            verify.send_verification(user)
            steps.append(f"open the link we sent to {user.email} to confirm your email")
        else:
            user.email_verified_at = verify.now()
        if needs_approval:
            steps.append("your administrator will approve your account and choose your role")
        db.session.commit()
    if not steps:
        return {"message": f"Account created at {business.name}. You can now sign in."}
    return {
        "message": f"Account created at {business.name}. Next, "
        + " and ".join(steps)
        + ". Then you can sign in."
    }


@blp.route("/login", methods=["POST"])
@limiter.limit(rate_limit, error_message=TOO_MANY)
@blp.arguments(LoginSchema)
@blp.response(200, LoginOut)
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
    if verify.verification_required() and not user.email_verified:
        abort(
            403,
            message="Confirm your email first: open the link we sent you, or ask for a new one.",
            reason="email_unverified",
        )
    if not user.is_approved:
        abort(
            403,
            message="Your administrator has not approved your account yet. We will email you "
            "as soon as they do.",
            reason="awaiting_approval",
        )
    if verify.code_required_for(user):
        challenge = verify.start_challenge(user)
        db.session.commit()
        return verify.challenge_answer(challenge, user)
    return start_session(user)


def open_challenge(challenge_id):
    challenge = db.session.scalar(
        db.select(LoginChallenge).filter_by(id=challenge_id).with_for_update()
    )
    if challenge is None or challenge.used_at or challenge.cancelled_at:
        db.session.rollback()
        abort(401, message="This sign-in has ended. Enter your email and password again.")
    if challenge.expires_at < verify.now():
        db.session.rollback()
        abort(401, message="This code has expired. Enter your email and password again.")
    return challenge


@blp.route("/login/verify", methods=["POST"])
@limiter.limit(rate_limit, error_message=TOO_MANY)
@blp.arguments(CodeIn)
@blp.response(200, SessionSchema)
@blp.doc(security=[])
def login_verify(data):
    challenge = open_challenge(data["challenge_id"])
    if not hmac.compare_digest(challenge.code_hash, verify.code_hash(challenge.id, data["code"])):
        challenge.attempts += 1
        left = verify.CODE_ATTEMPTS - challenge.attempts
        if left <= 0:
            challenge.cancelled_at = verify.now()
            db.session.commit()
            abort(401, message="Too many wrong codes. Enter your email and password again.")
        db.session.commit()
        abort(
            401,
            message=f"That code is not right. {left} {'try' if left == 1 else 'tries'} left.",
            reason="wrong_code",
        )
    challenge.used_at = verify.now()
    user = db.session.get(User, challenge.user_id)
    if not user.is_active:
        db.session.commit()
        abort(403, message="This account has been deactivated. Ask your administrator.")
    db.session.commit()
    return start_session(user)


@blp.route("/login/resend", methods=["POST"])
@limiter.limit(rate_limit, error_message=TOO_MANY)
@blp.arguments(ChallengeIn)
@blp.response(200, LoginOut)
@blp.doc(security=[])
def login_resend(data):
    challenge = open_challenge(data["challenge_id"])
    wait = verify.RESEND_SECONDS - int((verify.now() - challenge.sent_at).total_seconds())
    if wait > 0:
        db.session.rollback()
        abort(429, message=f"Wait {wait} seconds before asking for a new code.")
    if challenge.sends >= verify.MAX_SENDS:
        challenge.cancelled_at = verify.now()
        db.session.commit()
        abort(401, message="Too many codes sent. Enter your email and password again.")
    code = verify.new_code()
    challenge.code_hash = verify.code_hash(challenge.id, code)
    challenge.sent_at = verify.now()
    challenge.expires_at = verify.now() + timedelta(minutes=verify.CODE_MINUTES)
    challenge.sends += 1
    user = db.session.get(User, challenge.user_id)
    verify.email_code(user, code)
    db.session.commit()
    return verify.challenge_answer(challenge, user)


@blp.route("/verify-email", methods=["POST"])
@limiter.limit(rate_limit, error_message=TOO_MANY)
@blp.arguments(TokenIn)
@blp.response(200, MessageSchema)
@blp.doc(security=[])
def verify_email(data):
    row = verify.use_verification(data["token"])
    if row is None:
        db.session.rollback()
        abort(
            400,
            message="This link has expired or was already used. Ask for a new one.",
            reason="link_invalid",
        )
    user = db.session.get(User, row.user_id)
    if user.email_verified_at is None:
        user.email_verified_at = verify.now()
    db.session.commit()
    return {"message": "Your email is confirmed. You can now sign in."}


VERIFY_SENT = "If that email has an account waiting to be confirmed, we sent a new link."


@blp.route("/resend-verification", methods=["POST"])
@limiter.limit(rate_limit, error_message=TOO_MANY)
@blp.arguments(EmailIn)
@blp.response(200, MessageSchema)
@blp.doc(security=[])
def resend_verification(data):
    user = find_user(data["email"])
    if user is not None and user.is_active and not user.email_verified:
        verify.send_verification(user)
        db.session.commit()
    return {"message": VERIFY_SENT}


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
    current_user.session_version += 1
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
    if user.email_verified_at is None:
        user.email_verified_at = now
    reset.used_at = now
    db.session.commit()
    return {"message": "Password changed. You can now sign in."}
