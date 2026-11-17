from flask_smorest import Blueprint
from marshmallow import fields, validate

from app.auth import roles_required
from app.crud import PageQuery, delete, get_or_404, page_schema, paginate, save
from app.extensions import db
from app.models import Category
from app.schemas import Schema

blp = Blueprint("categories", __name__, url_prefix="/api/categories", description="Categories")


class CategorySchema(Schema):
    id = fields.Integer(dump_only=True)
    name = fields.String(required=True, validate=validate.Length(min=1, max=100))


@blp.route("/")
@blp.arguments(PageQuery, location="query")
@blp.response(200, page_schema(CategorySchema))
@roles_required()
def list_categories(args):
    query = db.select(Category).order_by(Category.name)
    return paginate(query, args["page"], args["per_page"])


@blp.route("/", methods=["POST"])
@blp.arguments(CategorySchema)
@blp.response(201, CategorySchema)
@roles_required("admin", "inventory")
def create_category(data):
    return save(Category(**data), f"Category '{data['name']}' already exists")


@blp.route("/<int:category_id>")
@blp.response(200, CategorySchema)
@roles_required()
def get_category(category_id):
    return get_or_404(Category, category_id)


@blp.route("/<int:category_id>", methods=["PUT"])
@blp.arguments(CategorySchema)
@blp.response(200, CategorySchema)
@roles_required("admin", "inventory")
def update_category(data, category_id):
    category = get_or_404(Category, category_id)
    category.name = data["name"]
    return save(category, f"Category '{data['name']}' already exists")


@blp.route("/<int:category_id>", methods=["DELETE"])
@blp.response(204)
@roles_required("admin", "inventory")
def delete_category(category_id):
    category = get_or_404(Category, category_id)
    delete(category, "This category still has products. Move or delete them first.")
