"""Employee requests, purchases and purchase lines."""

from app.extensions import db
from app.models.base import Money, TimestampMixin, in_list

URGENCIES = ("low", "normal", "high", "urgent")
REQUEST_STATUSES = ("pending", "approved", "rejected")
PURCHASE_STATUSES = ("ordered", "received", "cancelled")


class Request(TimestampMixin, db.Model):
    """An employee asks for something; a Procurement Manager approves or rejects it."""

    __tablename__ = "requests"
    __table_args__ = (
        db.CheckConstraint("quantity > 0", name="quantity_positive"),
        in_list("urgency", URGENCIES, "urgency_valid"),
        in_list("status", REQUEST_STATUSES, "status_valid"),
    )

    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    item = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    urgency = db.Column(db.String(10), nullable=False, server_default="normal")
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(10), nullable=False, server_default="pending", index=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"))
    review_comment = db.Column(db.Text)
    reviewed_at = db.Column(db.DateTime(timezone=True))

    requester = db.relationship("User", foreign_keys=[requester_id])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])


class Purchase(TimestampMixin, db.Model):
    __tablename__ = "purchases"
    __table_args__ = (
        db.CheckConstraint("total >= 0", name="total_not_negative"),
        in_list("status", PURCHASE_STATUSES, "status_valid"),
    )

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(
        db.Integer, db.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_by = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status = db.Column(db.String(10), nullable=False, server_default="ordered", index=True)
    total = db.Column(Money, nullable=False, server_default="0")

    supplier = db.relationship("Supplier")
    items = db.relationship("PurchaseItem", back_populates="purchase", cascade="all, delete-orphan")


class PurchaseItem(db.Model):
    __tablename__ = "purchase_items"
    __table_args__ = (
        db.CheckConstraint("quantity > 0", name="quantity_positive"),
        db.CheckConstraint("unit_cost >= 0", name="unit_cost_not_negative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(
        db.Integer, db.ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(Money, nullable=False)

    purchase = db.relationship("Purchase", back_populates="items")
    product = db.relationship("Product")