from app.extensions import db
from app.models.base import Money, TenantMixin, in_list, reference

PAYMENT_METHODS = ("cash", "mpesa", "card")
SALE_STATUSES = ("completed", "voided")
MOVEMENT_TYPES = ("purchase", "sale", "adjustment", "sale_void")


class Sale(TenantMixin, db.Model):
    __tablename__ = "sales"
    __number_kind__ = "sale"
    __table_args__ = (
        db.UniqueConstraint("business_id", "number", name="uq_sales_number"),
        db.UniqueConstraint("business_id", "idempotency_key", name="uq_sales_idempotency_key"),
        db.CheckConstraint("total >= 0", name="total_not_negative"),
        in_list("payment_method", PAYMENT_METHODS, "payment_method_valid"),
        in_list("status", SALE_STATUSES, "status_valid"),
    )

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, nullable=False)
    attendant_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    total = db.Column(Money, nullable=False)
    vat_rate = db.Column(db.Numeric(5, 2), nullable=False, server_default="0", default=0)
    vat_amount = db.Column(Money, nullable=False, server_default="0", default=0)
    payment_method = db.Column(db.String(10), nullable=False)
    payment_reference = db.Column(db.String(30))
    status = db.Column(db.String(10), nullable=False, server_default="completed", index=True)
    idempotency_key = db.Column(db.String(64))
    voided_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"))
    voided_at = db.Column(db.DateTime(timezone=True))
    void_reason = db.Column(db.Text)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), index=True
    )

    items = db.relationship(
        "SaleItem", back_populates="sale", cascade="all, delete-orphan", order_by="SaleItem.id"
    )
    attendant = db.relationship("User", foreign_keys=[attendant_id])
    voider = db.relationship("User", foreign_keys=[voided_by])

    @property
    def reference(self):
        return reference("S", self.number)


class SaleItem(TenantMixin, db.Model):
    __tablename__ = "sale_items"
    __table_args__ = (
        db.CheckConstraint("quantity > 0", name="quantity_positive"),
        db.CheckConstraint("unit_price >= 0", name="unit_price_not_negative"),
        db.CheckConstraint("unit_cost >= 0", name="unit_cost_not_negative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(
        db.Integer, db.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(Money, nullable=False)
    unit_cost = db.Column(Money, nullable=False)

    sale = db.relationship("Sale", back_populates="items")
    product = db.relationship("Product")


class StockMovement(TenantMixin, db.Model):
    __tablename__ = "stock_movements"
    __table_args__ = (
        db.CheckConstraint("change <> 0", name="change_not_zero"),
        db.CheckConstraint("quantity_after >= 0", name="quantity_after_not_negative"),
        in_list("type", MOVEMENT_TYPES, "type_valid"),
    )

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    change = db.Column(db.Integer, nullable=False)
    quantity_after = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(12), nullable=False, index=True)
    reference = db.Column(db.String(30))
    reason = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), index=True
    )

    product = db.relationship("Product", back_populates="movements")
    user = db.relationship("User")
