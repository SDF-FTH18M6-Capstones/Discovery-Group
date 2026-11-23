from app.extensions import db
from app.models.base import Money, TenantMixin, TimestampMixin, in_list, reference

URGENCIES = ("low", "normal", "high", "urgent")
URGENCY_RANK = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
REQUEST_STATUSES = ("pending", "approved", "rejected", "fulfilled", "cancelled")
ACTIVE_REQUEST_STATUSES = ("pending", "approved")
PURCHASE_STATUSES = ("draft", "ordered", "partially_received", "received", "cancelled")
OPEN_PURCHASE_STATUSES = ("draft", "ordered", "partially_received")


class Request(TenantMixin, TimestampMixin, db.Model):
    __tablename__ = "requests"
    __number_kind__ = "request"
    __table_args__ = (
        db.UniqueConstraint("business_id", "number", name="uq_requests_number"),
        db.CheckConstraint("quantity > 0", name="quantity_positive"),
        in_list("urgency", URGENCIES, "urgency_valid"),
        in_list("status", REQUEST_STATUSES, "status_valid"),
    )

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, nullable=False)
    requester_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="SET NULL"))
    item = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    urgency = db.Column(db.String(10), nullable=False, server_default="normal")
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(10), nullable=False, server_default="pending", index=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"))
    review_comment = db.Column(db.Text)
    reviewed_at = db.Column(db.DateTime(timezone=True))
    fulfilled_at = db.Column(db.DateTime(timezone=True))
    cancelled_at = db.Column(db.DateTime(timezone=True))

    requester = db.relationship("User", foreign_keys=[requester_id])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])
    product = db.relationship("Product")
    purchases = db.relationship("Purchase", back_populates="request")

    @property
    def reference(self):
        return reference("REQ", self.number)


class Purchase(TenantMixin, TimestampMixin, db.Model):
    __tablename__ = "purchases"
    __number_kind__ = "purchase"
    __table_args__ = (
        db.UniqueConstraint("business_id", "number", name="uq_purchases_number"),
        db.CheckConstraint("total >= 0", name="total_not_negative"),
        in_list("status", PURCHASE_STATUSES, "status_valid"),
    )

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, nullable=False)
    supplier_id = db.Column(
        db.Integer, db.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_by = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    request_id = db.Column(
        db.Integer, db.ForeignKey("requests.id", ondelete="SET NULL"), index=True
    )
    status = db.Column(db.String(20), nullable=False, server_default="draft", index=True)
    total = db.Column(Money, nullable=False, server_default="0")
    notes = db.Column(db.Text)
    ordered_at = db.Column(db.DateTime(timezone=True))
    received_at = db.Column(db.DateTime(timezone=True))
    cancelled_at = db.Column(db.DateTime(timezone=True))
    cancel_reason = db.Column(db.Text)

    supplier = db.relationship("Supplier")
    creator = db.relationship("User")
    request = db.relationship("Request", back_populates="purchases")
    items = db.relationship(
        "PurchaseItem",
        back_populates="purchase",
        cascade="all, delete-orphan",
        order_by="PurchaseItem.id",
    )
    receipts = db.relationship(
        "GoodsReceipt", back_populates="purchase", order_by="GoodsReceipt.id"
    )

    @property
    def reference(self):
        return reference("PO", self.number)


class PurchaseItem(TenantMixin, db.Model):
    __tablename__ = "purchase_items"
    __table_args__ = (
        db.CheckConstraint("quantity > 0", name="quantity_positive"),
        db.CheckConstraint("unit_cost >= 0", name="unit_cost_not_negative"),
        db.CheckConstraint(
            "received_quantity >= 0 AND received_quantity <= quantity", name="received_in_range"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(
        db.Integer, db.ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity = db.Column(db.Integer, nullable=False)
    received_quantity = db.Column(db.Integer, nullable=False, server_default="0", default=0)
    unit_cost = db.Column(Money, nullable=False)

    purchase = db.relationship("Purchase", back_populates="items")
    product = db.relationship("Product")

    @property
    def outstanding(self):
        return self.quantity - (self.received_quantity or 0)


class GoodsReceipt(TenantMixin, db.Model):

    __tablename__ = "goods_receipts"
    __number_kind__ = "grn"
    __table_args__ = (
        db.UniqueConstraint("business_id", "number", name="uq_goods_receipts_number"),
        db.UniqueConstraint(
            "business_id", "idempotency_key", name="uq_goods_receipts_idempotency_key"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, nullable=False)
    purchase_id = db.Column(
        db.Integer, db.ForeignKey("purchases.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    received_by = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key = db.Column(db.String(64))
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    purchase = db.relationship("Purchase", back_populates="receipts")
    receiver = db.relationship("User")
    items = db.relationship(
        "GoodsReceiptItem", back_populates="receipt", cascade="all, delete-orphan"
    )

    @property
    def reference(self):
        return reference("GRN", self.number)


class GoodsReceiptItem(TenantMixin, db.Model):
    __tablename__ = "goods_receipt_items"
    __table_args__ = (db.CheckConstraint("quantity > 0", name="quantity_positive"),)

    id = db.Column(db.Integer, primary_key=True)
    receipt_id = db.Column(
        db.Integer,
        db.ForeignKey("goods_receipts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    purchase_item_id = db.Column(
        db.Integer, db.ForeignKey("purchase_items.id", ondelete="RESTRICT"), nullable=False
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity = db.Column(db.Integer, nullable=False)

    receipt = db.relationship("GoodsReceipt", back_populates="items")
    product = db.relationship("Product")
