"""Categories, products and suppliers."""

from app.extensions import db
from app.models.base import Money, TimestampMixin


class Category(TimestampMixin, db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

    products = db.relationship("Product", back_populates="category")


class Product(TimestampMixin, db.Model):
    __tablename__ = "products"
    __table_args__ = (
        db.CheckConstraint("quantity >= 0", name="quantity_not_negative"),
        db.CheckConstraint("reorder_level >= 0", name="reorder_level_not_negative"),
        db.CheckConstraint("cost_price >= 0", name="cost_price_not_negative"),
        db.CheckConstraint("selling_price >= 0", name="selling_price_not_negative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(40), nullable=False, unique=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    category_id = db.Column(
        db.Integer, db.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    image_url = db.Column(db.String(500))
    cost_price = db.Column(Money, nullable=False)
    selling_price = db.Column(Money, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, server_default="0")
    reorder_level = db.Column(db.Integer, nullable=False, server_default="0")

    category = db.relationship("Category", back_populates="products")

    @property
    def is_low_stock(self) -> bool:
        return self.quantity <= self.reorder_level


class Supplier(TimestampMixin, db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    email = db.Column(db.String(255))
    phone = db.Column(db.String(30))