from flask_smorest import Blueprint, abort
from marshmallow import Schema, fields, validate

from app.auth import roles_required
from app.crud import PageQuery, delete, get_or_404, page_schema, paginate, save
from app.extensions import db
from app.models import Category, Product

blp = Blueprint("products", __name__, url_prefix="/api/products", description="Products")

money = {"places": 2, "as_string": True, "validate": validate.Range(min=0)}


class ProductSchema(Schema):
    id = fields.Integer(dump_only=True)
    sku = fields.String(required=True, validate=validate.Length(min=1, max=40))
    name = fields.String(required=True, validate=validate.Length(min=1, max=150))
    category_id = fields.Integer(required=True)
    category_name = fields.String(attribute="category.name", dump_only=True)
    image_url = fields.Url(allow_none=True, load_default=None)
    cost_price = fields.Decimal(required=True, **money)
    selling_price = fields.Decimal(required=True, **money)
    quantity = fields.Integer(load_default=0, validate=validate.Range(min=0))
    reorder_level = fields.Integer(load_default=0, validate=validate.Range(min=0))
    is_low_stock = fields.Boolean(dump_only=True)


class ProductQuery(PageQuery):
    search = fields.String(load_default=None)
    category_id = fields.Integer(load_default=None)
    low_stock = fields.Boolean(load_default=False)


def check_category(category_id):
    if db.session.get(Category, category_id) is None:
        abort(400, message=f"Category {category_id} does not exist")


@blp.route("/")
@blp.arguments(ProductQuery, location="query")
@blp.response(200, page_schema(ProductSchema))
@roles_required()
def list_products(args):
    query = db.select(Product).order_by(Product.name)
    if args["search"]:
        term = f"%{args['search']}%"
        query = query.where(Product.name.ilike(term) | Product.sku.ilike(term))
    if args["category_id"]:
        query = query.where(Product.category_id == args["category_id"])
    if args["low_stock"]:
        query = query.where(Product.quantity <= Product.reorder_level)
    return paginate(query, args["page"], args["per_page"])


@blp.route("/", methods=["POST"])
@blp.arguments(ProductSchema)
@blp.response(201, ProductSchema)
@roles_required("admin", "inventory")
def create_product(data):
    check_category(data["category_id"])
    return save(Product(**data), f"SKU '{data['sku']}' is already used")


@blp.route("/<int:product_id>")
@blp.response(200, ProductSchema)
@roles_required()
def get_product(product_id):
    return get_or_404(Product, product_id)


@blp.route("/<int:product_id>", methods=["PUT"])
@blp.arguments(ProductSchema)
@blp.response(200, ProductSchema)
@roles_required("admin", "inventory")
def update_product(data, product_id):
    product = get_or_404(Product, product_id)
    check_category(data["category_id"])
    for key, value in data.items():
        setattr(product, key, value)
    return save(product, f"SKU '{data['sku']}' is already used")


@blp.route("/<int:product_id>", methods=["DELETE"])
@blp.response(204)
@roles_required("admin", "inventory")
def delete_product(product_id):
    product = get_or_404(Product, product_id)
    delete(product, "This product has sales or purchases and cannot be deleted.")