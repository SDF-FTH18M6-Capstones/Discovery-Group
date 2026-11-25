from flask_smorest import Blueprint
from marshmallow import fields, validate

from app.auth import roles_required
from app.crud import PageQuery, delete, get_or_404, page_schema, paginate, save
from app.extensions import db
from app.models import Supplier
from app.schemas import Schema

blp = Blueprint("suppliers", __name__, url_prefix="/api/suppliers", description="Suppliers")


class SupplierSchema(Schema):
    id = fields.Integer(dump_only=True)
    code = fields.String(dump_only=True)
    name = fields.String(required=True, validate=validate.Length(min=1, max=150))
    email = fields.Email(allow_none=True, load_default=None)
    phone = fields.String(
        allow_none=True,
        load_default=None,
        validate=validate.Regexp(r"^\+?[0-9 ]{7,20}$", error="Enter a valid phone number."),
    )
    address = fields.String(allow_none=True, load_default=None, validate=validate.Length(max=300))
    is_active = fields.Boolean(load_default=True)


class SupplierQuery(PageQuery):
    search = fields.String(load_default=None)
    active = fields.Boolean(load_default=None)


@blp.route("/")
@blp.arguments(SupplierQuery, location="query")
@blp.response(200, page_schema(SupplierSchema))
@roles_required("admin", "procurement")
def list_suppliers(args):
    query = db.select(Supplier).order_by(Supplier.name)
    if args["search"]:
        term = f"%{args['search']}%"
        code = args["search"].upper().removeprefix("SUP-").lstrip("0")
        match = Supplier.name.ilike(term) | Supplier.email.ilike(term)
        if code.isdigit():
            match = match | (Supplier.number == int(code))
        query = query.where(match)
    if args["active"] is not None:
        query = query.where(Supplier.is_active.is_(args["active"]))
    return paginate(query, args["page"], args["per_page"])


@blp.route("/", methods=["POST"])
@blp.arguments(SupplierSchema)
@blp.response(201, SupplierSchema)
@roles_required("admin", "procurement")
def create_supplier(data):
    return save(Supplier(**data), "Could not save this supplier")


@blp.route("/<int:supplier_id>")
@blp.response(200, SupplierSchema)
@roles_required("admin", "procurement")
def get_supplier(supplier_id):
    return get_or_404(Supplier, supplier_id)


@blp.route("/<int:supplier_id>", methods=["PUT"])
@blp.arguments(SupplierSchema)
@blp.response(200, SupplierSchema)
@roles_required("admin", "procurement")
def update_supplier(data, supplier_id):
    supplier = get_or_404(Supplier, supplier_id)
    for key, value in data.items():
        setattr(supplier, key, value)
    return save(supplier, "Could not save this supplier")


@blp.route("/<int:supplier_id>", methods=["DELETE"])
@blp.response(204)
@roles_required("admin", "procurement")
def delete_supplier(supplier_id):
    supplier = get_or_404(Supplier, supplier_id)
    delete(
        supplier,
        "This supplier has purchase orders and cannot be deleted. Mark it inactive instead.",
    )
