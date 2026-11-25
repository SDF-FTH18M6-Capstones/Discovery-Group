import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from flask import current_app

from app.extensions import db
from app.mail import queue_email
from app.models import EmailVerification, LoginChallenge

VERIFY_HOURS = 24
CODE_MINUTES = 5
CODE_ATTEMPTS = 5
RESEND_SECONDS = 60
MAX_SENDS = 5


def now():
    return datetime.now(UTC)


def sha256(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def verification_required():
    return current_app.config["EMAIL_VERIFICATION_REQUIRED"]


def send_verification(user):
    db.session.execute(
        db.update(EmailVerification)
        .where(EmailVerification.user_id == user.id, EmailVerification.used_at.is_(None))
        .values(used_at=now())
    )
    raw = secrets.token_urlsafe(32)
    db.session.add(
        EmailVerification(
            user_id=user.id,
            token_hash=sha256(raw),
            expires_at=now() + timedelta(hours=VERIFY_HOURS),
        )
    )
    link = f"{current_app.config['FRONTEND_URL']}/verify-email?token={raw}"
    queue_email(
        user.email,
        "Confirm your StockPilot email",
        f"Hello {user.full_name},\n\nWelcome to StockPilot. Open this link within "
        f"{VERIFY_HOURS} hours to confirm your email and activate your account:\n\n{link}\n\n"
        "If you did not sign up, ignore this email.\n\n— StockPilot",
    )


def use_verification(raw_token):
    row = db.session.scalar(
        db.select(EmailVerification).filter_by(token_hash=sha256(raw_token)).with_for_update()
    )
    if row is None or row.used_at is not None or row.expires_at < now():
        return None
    row.used_at = now()
    return row


def code_required_for(user):
    if not current_app.config["LOGIN_CODE_REQUIRED"]:
        return False
    domain = user.email.rsplit("@", 1)[-1].lower()
    return domain not in current_app.config["LOGIN_CODE_EXEMPT_DOMAINS"]


def code_hash(challenge_id, code):
    key = current_app.config["SECRET_KEY"].encode()
    return hmac.new(key, f"{challenge_id}:{code}".encode(), hashlib.sha256).hexdigest()


def new_code():
    return f"{secrets.randbelow(10**6):06d}"


def email_code(user, code):
    queue_email(
        user.email,
        f"Your StockPilot sign-in code: {code}",
        f"Hello {user.full_name},\n\nYour sign-in code is:\n\n    {code}\n\n"
        f"It works once and expires in {CODE_MINUTES} minutes. If you did not try to sign in, "
        "change your password: someone knows it.\n\n— StockPilot",
    )


def start_challenge(user):
    db.session.execute(
        db.update(LoginChallenge)
        .where(
            LoginChallenge.user_id == user.id,
            LoginChallenge.used_at.is_(None),
            LoginChallenge.cancelled_at.is_(None),
        )
        .values(cancelled_at=now())
    )
    challenge = LoginChallenge(
        id=secrets.token_hex(16),
        user_id=user.id,
        code_hash="",
        expires_at=now() + timedelta(minutes=CODE_MINUTES),
        sent_at=now(),
        attempts=0,
        sends=1,
    )
    code = new_code()
    challenge.code_hash = code_hash(challenge.id, code)
    db.session.add(challenge)
    email_code(user, code)
    return challenge


def mask_email(email):
    name, _, domain = email.partition("@")
    shown = name[:1] + "•" * max(len(name) - 1, 2)
    return f"{shown}@{domain}"


def challenge_answer(challenge, user):
    return {
        "code_required": True,
        "challenge_id": challenge.id,
        "email_hint": mask_email(user.email),
        "expires_in": CODE_MINUTES * 60,
        "resend_after": RESEND_SECONDS,
    }


def is_open(challenge):
    return (
        challenge is not None
        and challenge.used_at is None
        and challenge.cancelled_at is None
        and challenge.expires_at > now()
    )
