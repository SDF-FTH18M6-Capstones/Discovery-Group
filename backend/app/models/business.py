import secrets
import uuid

from app.extensions import db
from app.models.base import Money, TenantMixin, TimestampMixin, in_list

JOIN_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_join_code() -> str:
    return "".join(secrets.choice(JOIN_CODE_ALPHABET) for _ in range(8))


class Business(TimestampMixin, db.Model):
    __tablename__ = "businesses"
    __table_args__ = (
        db.CheckConstraint("vat_rate >= 0 AND vat_rate < 100", name="vat_rate_valid"),
        in_list("mpesa_type", ("paybill", "till"), "mpesa_type_valid"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    join_code = db.Column(db.String(12), nullable=False, unique=True, default=new_join_code)
    timezone = db.Column(db.String(64), nullable=False, server_default="Africa/Nairobi")
    currency = db.Column(db.String(3), nullable=False, server_default="KES")
    vat_rate = db.Column(db.Numeric(5, 2), nullable=False, server_default="16")
    phone = db.Column(db.String(30))
    email = db.Column(db.String(255))
    address = db.Column(db.String(300))
    receipt_footer = db.Column(db.String(300))
    is_active = db.Column(db.Boolean, nullable=False, server_default=db.true())
    daily_summary = db.Column(db.Boolean, nullable=False, server_default=db.true(), default=True)
    summary_sent_on = db.Column(db.Date)
    trial_ends_on = db.Column(db.Date)
    paid_until = db.Column(db.Date)
    mpesa_mode = db.Column(db.String(10))
    mpesa_type = db.Column(db.String(10), nullable=False, server_default="paybill")
    mpesa_shortcode = db.Column(db.String(20))
    mpesa_till = db.Column(db.String(20))
    mpesa_passkey = db.Column(db.Text)
    mpesa_consumer_key = db.Column(db.Text)
    mpesa_consumer_secret = db.Column(db.Text)


class DocumentCounter(db.Model):
    __tablename__ = "document_counters"

    business_id = db.Column(
        db.Integer, db.ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True
    )
    kind = db.Column(db.String(20), primary_key=True)
    last = db.Column(db.Integer, nullable=False)


class RevokedToken(db.Model):
    __tablename__ = "revoked_tokens"

    jti = db.Column(db.String(64), primary_key=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)


class PasswordReset(db.Model):
    __tablename__ = "password_resets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())


class EmailVerification(db.Model):
    __tablename__ = "email_verifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())


class LoginChallenge(db.Model):
    __tablename__ = "login_challenges"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code_hash = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    sent_at = db.Column(db.DateTime(timezone=True), nullable=False)
    attempts = db.Column(db.Integer, nullable=False, server_default="0", default=0)
    sends = db.Column(db.Integer, nullable=False, server_default="1", default=1)
    used_at = db.Column(db.DateTime(timezone=True))
    cancelled_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    user = db.relationship("User")


class AuditLog(TenantMixin, db.Model):
    __tablename__ = "audit_logs"
    __table_args__ = (db.Index("ix_audit_logs_entity", "entity_type", "entity_id"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    action = db.Column(db.String(40), nullable=False)
    entity_type = db.Column(db.String(30), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    summary = db.Column(db.Text, nullable=False)
    changes = db.Column(db.JSON)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), index=True
    )

    user = db.relationship("User")


class Image(TenantMixin, db.Model):
    __tablename__ = "images"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    content_type = db.Column(db.String(30), nullable=False)
    data = db.Column(db.LargeBinary, nullable=False)
    width = db.Column(db.Integer, nullable=False)
    height = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())


class Expense(TenantMixin, TimestampMixin, db.Model):
    __tablename__ = "expenses"
    __table_args__ = (db.CheckConstraint("amount > 0", name="amount_positive"),)

    id = db.Column(db.Integer, primary_key=True)
    spent_on = db.Column(db.Date, nullable=False, index=True)
    category = db.Column(db.String(60), nullable=False)
    description = db.Column(db.String(300))
    amount = db.Column(Money, nullable=False)
    created_by = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    creator = db.relationship("User")
