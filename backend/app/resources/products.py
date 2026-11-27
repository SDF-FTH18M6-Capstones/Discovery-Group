from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import fields, validate
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.audit import audit, diff
from app.auth import roles_required
from app.crud import PageQuery, delete, find, get_or_404, page_schema, paginate, save
from app.extensions import db
from app.images import read_upload, remove_photo, replace_photo
from app.models import Category, Product, PurchaseItem, SaleItem, StockMovement, Supplier
from app.schemas import Schema
from app.stockledger import move_stock
from app.timeline import TimelineEntry, product_timeline

blp = Blueprint("products", __name__, url_prefix="/api/products", description="Products")

money = {"places": 2, "as_string": True, "validate": validate.Range(min=0)}
EDITORS = ("inventory",)
CREATORS = ("inventory", "procurement")
SEE_ALL = ("admin", "inventory")
TRACKED = (
    "sku",
    "name",
    "category_id",
    "cost_price",
    "selling_price",
    "reorder_level",
    "reorder_quantity",
    "default_supplier_id",
)


class ProductSchema(Schema):
    id = fields.Integer(dump_only=True)
    sku = fields.String(required=True, validate=validate.Length(min=1, max=40))
    name = fields.String(required=True, validate=validate.Length(min=1, max=150))
    category_id = fields.Integer(required=True)
    category_name = fields.String(attribute="category.name", dump_only=True)
    image_url = fields.String(dump_only=True)
    cost_price = fields.Decimal(required=True, **money)
    selling_price = fields.Decimal(required=True, **money)
    quantity = fields.Integer(load_default=0, validate=validate.Range(min=0))
    reorder_level = fields.Integer(load_default=0, validate=validate.Range(min=0))
    reorder_quantity = fields.Integer(
        load_default=None, allow_none=True, validate=validate.Range(min=1, max=100000)
    )
    default_supplier_id = fields.Integer(load_default=None, allow_none=True)
    default_supplier_name = fields.String(
        attribute="default_supplier.name", dump_only=True, allow_none=True
    )
    is_active = fields.Boolean(dump_only=True)
    is_low_stock = fields.Boolean(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class ProductQuery(PageQuery):
    search = fields.String(load_default=None)
    category_id = fields.Integer(load_default=None)
    low_stock = fields.Boolean(load_default=False)
    status = fields.String(
        load_default="active", validate=validate.OneOf(("active", "retired", "all"))
    )
    in_stock = fields.Boolean(load_default=False)


def check_category(category_id):
    if find(Category, category_id) is None:
        abort(400, message=f"Category {category_id} does not exist")


def check_supplier(supplier_id):
    if supplier_id is not None and find(Supplier, supplier_id) is None:
        abort(400, message=f"Supplier {supplier_id} does not exist")


@blp.route("/")
@blp.arguments(ProductQuery, location="query")
@blp.response(200, page_schema(ProductSchema))
@roles_required()
def list_products(args):
    query = db.select(Product).options(selectinload(Product.category)).order_by(Product.name)
    if args["search"]:
        term = f"%{args['search']}%"
        query = query.where(Product.name.ilike(term) | Product.sku.ilike(term))
    if args["category_id"]:
        query = query.where(Product.category_id == args["category_id"])
    if args["low_stock"]:
        query = query.where(Product.quantity <= Product.reorder_level)
    if args["in_stock"]:
        query = query.where(Product.quantity > 0)
    if args["status"] != "all":
        query = query.where(Product.is_active.is_(args["status"] == "active"))
    return paginate(query, args["page"], args["per_page"])


@blp.route("/", methods=["POST"])
@blp.arguments(ProductSchema)
@blp.response(201, ProductSchema)
@roles_required(*CREATORS)
def create_product(data):
    check_category(data["category_id"])
    check_supplier(data["default_supplier_id"])
    opening = data.pop("quantity")
    product = Product(**data, quantity=0)
    db.session.add(product)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        abort(409, message=f"SKU '{data['sku']}' is already used")
    audit("created", "product", product.id, f"Product {product.sku} {product.name} created")
    if opening:
        move_stock(product, opening, "adjustment", current_user.id, reason="Opening stock")
    db.session.commit()
    return product


@blp.route("/<int:product_id>")
@blp.response(200, ProductSchema)
@roles_required()
def get_product(product_id):
    return get_or_404(Product, product_id)


@blp.route("/<int:product_id>", methods=["PUT"])
@blp.arguments(ProductSchema)
@blp.response(200, ProductSchema)
@roles_required(*EDITORS)
def update_product(data, product_id):
    product = get_or_404(Product, product_id)
    check_category(data["category_id"])
    check_supplier(data["default_supplier_id"])
    data.pop("quantity", None)
    changes = diff(product, data, TRACKED)
    for key, value in data.items():
        setattr(product, key, value)
    save(product, f"SKU '{data['sku']}' is already used")
    if changes:
        audit("updated", "product", product.id, f"{product.name} edited", changes)
        db.session.commit()
    return product


def has_history(product_id):
    for model in (StockMovement, SaleItem, PurchaseItem):
        if db.session.scalar(db.select(model.id).where(model.product_id == product_id).limit(1)):
            return True
    return False


@blp.route("/<int:product_id>", methods=["DELETE"])
@blp.response(204)
@roles_required(*EDITORS)
def delete_product(product_id):
    product = get_or_404(Product, product_id)
    if has_history(product_id):
        abort(
            409,
            message="This product has stock history (sales, purchases or adjustments). "
            "Retire it instead: it keeps its history and disappears from the till.",
        )
    image_holder = product.image_id
    delete(product, "This product is still in use and cannot be deleted.")
    if image_holder:
        remove_orphan_image(image_holder)


def remove_orphan_image(image_id):
    from app.models import Image

    db.session.execute(db.delete(Image).where(Image.id == image_id))
    db.session.commit()


def set_active(product_id, active):
    product = get_or_404(Product, product_id)
    if product.is_active != active:
        product.is_active = active
        word = "restored" if active else "retired"
        audit(
            word,
            "product",
            product.id,
            f"{product.name} {word}",
            {"is_active": [not active, active]},
        )
        db.session.commit()
    return product


@blp.route("/<int:product_id>/retire", methods=["POST"])
@blp.response(200, ProductSchema)
@roles_required(*EDITORS)
def retire_product(product_id):
    return set_active(product_id, False)


@blp.route("/<int:product_id>/restore", methods=["POST"])
@blp.response(200, ProductSchema)
@roles_required(*EDITORS)
def restore_product(product_id):
    return set_active(product_id, True)


@blp.route("/<int:product_id>/photo", methods=["POST"])
@blp.response(200, ProductSchema)
@blp.doc(
    requestBody={
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "properties": {"photo": {"type": "string", "format": "binary"}},
                }
            }
        }
    }
)
@roles_required(*EDITORS)
def upload_photo(product_id):
    product = get_or_404(Product, product_id)
    replace_photo(product, read_upload())
    audit("photo", "product", product.id, f"{product.name}: photo changed")
    db.session.commit()
    return product


@blp.route("/<int:product_id>/photo", methods=["DELETE"])
@blp.response(200, ProductSchema)
@roles_required(*EDITORS)
def delete_photo(product_id):
    product = get_or_404(Product, product_id)
    remove_photo(product)
    db.session.commit()
    return product


@blp.route("/<int:product_id>/timeline")
@blp.arguments(PageQuery, location="query")
@blp.response(200, page_schema(TimelineEntry))
@roles_required(*SEE_ALL)
def timeline(args, product_id):
    get_or_404(Product, product_id)
    return product_timeline(product_id, args["page"], args["per_page"])
