from app.extensions import db
from app.models.base import Money, TenantMixin, TimestampMixin, reference


class Category(TenantMixin, TimestampMixin, db.Model):
    __tablename__ = "categories"
    __table_args__ = (db.UniqueConstraint("business_id", "name", name="uq_categories_name"),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, server_default=db.true())

    products = db.relationship("Product", back_populates="category")


class Product(TenantMixin, TimestampMixin, db.Model):
    __tablename__ = "products"
    __table_args__ = (
        db.UniqueConstraint("business_id", "sku", name="uq_products_sku"),
        db.CheckConstraint("quantity >= 0", name="quantity_not_negative"),
        db.CheckConstraint("reorder_level >= 0", name="reorder_level_not_negative"),
        db.CheckConstraint("cost_price >= 0", name="cost_price_not_negative"),
        db.CheckConstraint("selling_price >= 0", name="selling_price_not_negative"),
        db.CheckConstraint("reorder_quantity > 0", name="reorder_quantity_positive"),
    )

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(40), nullable=False)
    name = db.Column(db.String(150), nullable=False, index=True)
    category_id = db.Column(
        db.Integer, db.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    image_url = db.Column(db.String(500))
    image_id = db.Column(db.String(36), db.ForeignKey("images.id", ondelete="SET NULL"))
    cost_price = db.Column(Money, nullable=False)
    selling_price = db.Column(Money, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, server_default="0")
    reorder_level = db.Column(db.Integer, nullable=False, server_default="0")
    reorder_quantity = db.Column(db.Integer)
    default_supplier_id = db.Column(
        db.Integer, db.ForeignKey("suppliers.id", ondelete="SET NULL"), index=True
    )
    is_active = db.Column(db.Boolean, nullable=False, server_default=db.true(), index=True)

    category = db.relationship("Category", back_populates="products")
    default_supplier = db.relationship("Supplier")
    movements = db.relationship("StockMovement", back_populates="product")

    @property
    def is_low_stock(self) -> bool:
        return self.quantity <= self.reorder_level


class Supplier(TenantMixin, TimestampMixin, db.Model):
    __tablename__ = "suppliers"
    __number_kind__ = "supplier"
    __table_args__ = (db.UniqueConstraint("business_id", "number", name="uq_suppliers_number"),)

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(150), nullable=False, index=True)
    email = db.Column(db.String(255))
    phone = db.Column(db.String(30))
    address = db.Column(db.String(300))
    is_active = db.Column(db.Boolean, nullable=False, server_default=db.true())

    @property
    def code(self):
        return reference("SUP", self.number, 3)
