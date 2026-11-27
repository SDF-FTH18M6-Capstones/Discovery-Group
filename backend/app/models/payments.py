from app.extensions import db
from app.models.base import TenantMixin, in_list

MPESA_STATUSES = ("pending", "paid", "failed", "cancelled")


class MpesaPayment(TenantMixin, db.Model):
    __tablename__ = "mpesa_payments"
    __table_args__ = (
        db.UniqueConstraint(
            "business_id", "idempotency_key", name="uq_mpesa_payments_idempotency_key"
        ),
        db.CheckConstraint("amount > 0", name="amount_positive"),
        in_list("status", MPESA_STATUSES, "status_valid"),
    )

    id = db.Column(db.Integer, primary_key=True)
    attendant_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    phone = db.Column(db.String(15), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    items = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(12), nullable=False, server_default="pending", default="pending")
    simulated = db.Column(db.Boolean, nullable=False, server_default=db.false(), default=False)
    checkout_request_id = db.Column(db.String(80), unique=True)
    merchant_request_id = db.Column(db.String(80))
    receipt_number = db.Column(db.String(20), unique=True)
    result_code = db.Column(db.Integer)
    result_desc = db.Column(db.String(255))
    problem = db.Column(db.Text)
    idempotency_key = db.Column(db.String(64))
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id", ondelete="SET NULL"), index=True)
    checked_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), index=True
    )

    attendant = db.relationship("User")
    sale = db.relationship("Sale")
