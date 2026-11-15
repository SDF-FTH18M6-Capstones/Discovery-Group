"""Sales, sale lines and the stock history."""

from app.extensions import db
from app.models.base import Money, in_list

PAYMENT_METHODS = ("cash", "mpesa", "card")
MOVEMENT_TYPES = ("purchase", "sale", "adjustment")


class Sale(db.Model):
    __tablename__ = "sales"
    __table_args__ = (
        db.CheckConstraint("total >= 0", name="total_not_negative"),
        in_list("payment_method", PAYMENT_METHODS, "payment_method_valid"),
    )

    id = db.Column(db.Integer, primary_key=True)
    attendant_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    total = db.Column(Money, nullable=False)
    payment_method = db.Column(db.String(10), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), index=True
    )

    items = db.relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")


class SaleItem(db.Model):
    __tablename__ = "sale_items"
    __table_args__ = (
        db.CheckConstraint("quantity > 0", name="quantity_positive"),
        db.CheckConstraint("unit_price >= 0", name="unit_price_not_negative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(
        db.Integer, db.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(Money, nullable=False)  # copied at sale time

    sale = db.relationship("Sale", back_populates="items")
    product = db.relationship("Product")


class StockMovement(db.Model):
    """One row for every change to products.quantity."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        db.CheckConstraint("change <> 0", name="change_not_zero"),
        in_list("type", MOVEMENT_TYPES, "type_valid"),
    )

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    change = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(12), nullable=False)
    reason = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    product = db.relationship("Product")
    user = db.relationship("User")