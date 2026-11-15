"""/api/suppliers — GET (list, search), POST, GET one, PUT, DELETE."""

from flask_smorest import Blueprint
from marshmallow import Schema, fields, validate

from app.crud import PageQuery, delete, get_or_404, page_schema, paginate, save
from app.extensions import db
from app.models import Supplier

blp = Blueprint("suppliers", __name__, url_prefix="/api/suppliers", description="Suppliers")


class SupplierSchema(Schema):
    id = fields.Integer(dump_only=True)
    name = fields.String(required=True, validate=validate.Length(min=1, max=150))
    email = fields.Email(allow_none=True, load_default=None)
    phone = fields.String(
        allow_none=True,
        load_default=None,
        validate=validate.Regexp(r"^\+?[0-9 ]{7,20}$", error="Enter a valid phone number."),
    )


class SupplierQuery(PageQuery):
    search = fields.String(load_default=None)


@blp.route("/")
@blp.arguments(SupplierQuery, location="query")
@blp.response(200, page_schema(SupplierSchema))
def list_suppliers(args):
    query = db.select(Supplier).order_by(Supplier.name)
    if args["search"]:
        query = query.where(Supplier.name.ilike(f"%{args['search']}%"))
    return paginate(query, args["page"], args["per_page"])


@blp.route("/", methods=["POST"])
@blp.arguments(SupplierSchema)
@blp.response(201, SupplierSchema)
def create_supplier(data):
    return save(Supplier(**data), "Could not save this supplier")


@blp.route("/<int:supplier_id>")
@blp.response(200, SupplierSchema)
def get_supplier(supplier_id):
    return get_or_404(Supplier, supplier_id)


@blp.route("/<int:supplier_id>", methods=["PUT"])
@blp.arguments(SupplierSchema)
@blp.response(200, SupplierSchema)
def update_supplier(data, supplier_id):
    supplier = get_or_404(Supplier, supplier_id)
    for key, value in data.items():
        setattr(supplier, key, value)
    return save(supplier, "Could not save this supplier")


@blp.route("/<int:supplier_id>", methods=["DELETE"])
@blp.response(204)
def delete_supplier(supplier_id):
    supplier = get_or_404(Supplier, supplier_id)
    delete(supplier, "This supplier has purchase orders and cannot be deleted.")