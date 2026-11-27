import hashlib
import secrets
from datetime import UTC, datetime

from flask import request
from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import fields

from app.audit import audit
from app.auth import roles_required
from app.extensions import db, limiter
from app.models import PhoneLink
from app.money import import_entries, phone_batch
from app.schemas import Schema
from app.shoptime import day_bounds, shop_today
from app.statements import parse_sms
from app.tenancy import tenant

blp = Blueprint(
    "phone", __name__, url_prefix="/api/phone", description="M-Pesa messages sent by a phone"
)

TEXT_KEYS = ("text", "message", "body", "msg", "content")


class LinkOut(Schema):
    active = fields.Boolean()
    url = fields.String(allow_none=True)
    created_at = fields.DateTime(allow_none=True)
    last_message_at = fields.DateTime(allow_none=True)
    messages = fields.Integer()


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def active_link():
    return db.session.scalar(
        db.select(PhoneLink)
        .where(PhoneLink.revoked_at.is_(None))
        .order_by(PhoneLink.id.desc())
        .limit(1)
    )


def described(link, url=None):
    if link is None:
        return {"active": False, "url": None, "messages": 0}
    return {
        "active": True,
        "url": url,
        "created_at": link.created_at,
        "last_message_at": link.last_message_at,
        "messages": link.messages,
    }


@blp.route("/link")
@blp.response(200, LinkOut)
@roles_required("admin")
def show_link():
    return described(active_link())


@blp.route("/link", methods=["POST"])
@blp.response(201, LinkOut)
@roles_required("admin")
def create_link():
    now = datetime.now(UTC)
    for old in db.session.scalars(db.select(PhoneLink).where(PhoneLink.revoked_at.is_(None))):
        old.revoked_at = now
    token = secrets.token_urlsafe(24)
    link = PhoneLink(token_hash=digest(token), created_by=current_user.id, created_at=now)
    db.session.add(link)
    db.session.flush()
    audit("created", "phone_link", link.id, "Linked a phone to send M-Pesa messages")
    db.session.commit()
    return described(link, f"{request.host_url.rstrip('/')}/api/phone/inbox/{token}")


@blp.route("/link", methods=["DELETE"])
@blp.response(204)
@roles_required("admin")
def remove_link():
    link = active_link()
    if link is not None:
        link.revoked_at = datetime.now(UTC)
        audit("deleted", "phone_link", link.id, "Stopped taking M-Pesa messages from the phone")
        db.session.commit()


def message_of(payload):
    if isinstance(payload, dict):
        text = next((payload[k] for k in TEXT_KEYS if isinstance(payload.get(k), str)), "")
        return str(payload.get("from") or payload.get("sender") or ""), text
    return "", request.get_data(as_text=True)[:5000]


@blp.route("/inbox/<string:token>", methods=["POST"])
@limiter.limit("120/minute")
@blp.response(200)
@blp.doc(security=[])
def inbox(token):
    link = db.session.scalar(
        db.select(PhoneLink).where(
            PhoneLink.token_hash == digest(token), PhoneLink.revoked_at.is_(None)
        )
    )
    if link is None:
        abort(404)
    sender, text = message_of(request.get_json(silent=True) or request.form.to_dict() or None)
    if sender and "mpesa" not in sender.lower().replace("-", ""):
        return {"added": 0, "ignored": True}
    with tenant(link.business_id):
        entries, skipped = parse_sms(text)
        added = 0
        if entries:
            start, _ = day_bounds(shop_today())
            batch = phone_batch(link, start)
            before = batch.added
            import_entries(entries, skipped, "phone", None, link.creator, batch=batch)
            added = batch.added - before
        link.messages += 1
        link.last_message_at = datetime.now(UTC)
        db.session.commit()
    return {"added": added, "ignored": not entries}
