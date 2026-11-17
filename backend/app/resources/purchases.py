from decimal import Decimal

from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import fields, validate
from sqlalchemy.orm import selectinload

from app.auth import roles_required
from app.crud import PageQuery, get_or_404, page_schema, paginate
from app.extensions import db
from app.models import Product, Purchase, PurchaseItem, StockMovement, Supplier
from app.models.procurement import PURCHASE_STATUSES
from app.notify import notify
from app.schemas import Schema

blp = Blueprint("purchases", __name__, url_prefix="/api/purchases", description="Purchase orders")

BUYERS = ("admin", "procurement")
RECEIVERS = ("admin", "inventory")
VIEWERS = ("admin", "procurement", "inventory")
money = {"places": 2, "as_string": True}


class PurchaseLineIn(Schema):
    product_id = fields.Integer(required=True)
    quantity = fields.Integer(required=True, validate=validate.Range(min=1, max=100000))
    unit_cost = fields.Decimal(required=True, places=2, validate=validate.Range(min=0))


class PurchaseIn(Schema):
    supplier_id = fields.Integer(required=True)
    items = fields.List(
        fields.Nested(PurchaseLineIn),
        required=True,
        validate=validate.Length(min=1, max=100, error="Add at least one product."),
    )


class PurchaseLineOut(Schema):
    product_id = fields.Integer()
    product_name = fields.String(attribute="product.name")
    sku = fields.String(attribute="product.sku")
    quantity = fields.Integer()
    unit_cost = fields.Decimal(**money)


class PurchaseOut(Schema):
    id = fields.Integer()
    reference = fields.Method("get_reference")
    supplier_id = fields.Integer()
    supplier_name = fields.String(attribute="supplier.name")
    created_by = fields.Integer()
    creator_name = fields.String(attribute="creator.full_name")
    status = fields.String()
    total = fields.Decimal(**money)
    created_at = fields.DateTime()
    updated_at = fields.DateTime()
    items = fields.List(fields.Nested(PurchaseLineOut))

    def get_reference(self, purchase):
        return f"PO-{purchase.id:04d}"


class PurchaseQuery(PageQuery):
    status = fields.String(load_default=None, validate=validate.OneOf(PURCHASE_STATUSES))


def with_lines(query):
    return query.options(
        selectinload(Purchase.items).selectinload(PurchaseItem.product),
        selectinload(Purchase.supplier),
        selectinload(Purchase.creator),
    )


def load(purchase_id):
    get_or_404(Purchase, purchase_id)
    return db.session.scalar(with_lines(db.select(Purchase).where(Purchase.id == purchase_id)))


@blp.route("/")
@blp.arguments(PurchaseQuery, location="query")
@blp.response(200, page_schema(PurchaseOut))
@roles_required(*VIEWERS)
def list_purchases(args):
    query = with_lines(db.select(Purchase)).order_by(Purchase.created_at.desc(), Purchase.id.desc())
    if args["status"]:
        query = query.where(Purchase.status == args["status"])
    return paginate(query, args["page"], args["per_page"])


@blp.route("/", methods=["POST"])
@blp.arguments(PurchaseIn)
@blp.response(201, PurchaseOut)
@roles_required(*BUYERS)
def create_purchase(data):
    if db.session.get(Supplier, data["supplier_id"]) is None:
        abort(400, message=f"Supplier {data['supplier_id']} does not exist")
    product_ids = {line["product_id"] for line in data["items"]}
    found = set(db.session.scalars(db.select(Product.id).where(Product.id.in_(product_ids))))
    if product_ids - found:
        abort(400, message=f"Product {sorted(product_ids - found)[0]} does not exist")

    purchase = Purchase(supplier_id=data["supplier_id"], created_by=current_user.id, total=0)
    total = Decimal("0")
    for line in data["items"]:
        purchase.items.append(PurchaseItem(**line))
        total += line["unit_cost"] * line["quantity"]
    purchase.total = total
    db.session.add(purchase)
    db.session.commit()
    return load(purchase.id)


@blp.route("/<int:purchase_id>")
@blp.response(200, PurchaseOut)
@roles_required(*VIEWERS)
def get_purchase(purchase_id):
    return load(purchase_id)


def still_ordered(purchase_id):
    purchase = db.session.scalar(
        db.select(Purchase).where(Purchase.id == purchase_id).with_for_update()
    )
    if purchase is None:
        abort(404, message=f"Purchase {purchase_id} not found")
    if purchase.status != "ordered":
        db.session.rollback()
        abort(409, message=f"This order is already {purchase.status}.")
    return purchase


@blp.route("/<int:purchase_id>/receive", methods=["POST"])
@blp.response(200, PurchaseOut)
@roles_required(*RECEIVERS)
def receive_purchase(purchase_id):
    """Stock goes up only here, once, for every line of the order."""
    purchase = still_ordered(purchase_id)
    for line in purchase.items:
        product = db.session.scalar(
            db.select(Product).where(Product.id == line.product_id).with_for_update()
        )
        product.quantity += line.quantity
        db.session.add(
            StockMovement(
                product_id=product.id,
                change=line.quantity,
                type="purchase",
                reason=f"PO-{purchase.id:04d} received",
                user_id=current_user.id,
            )
        )
    purchase.status = "received"
    notify([purchase.created_by], f"PO-{purchase.id:04d} was received into stock.")
    db.session.commit()
    return load(purchase_id)


@blp.route("/<int:purchase_id>/cancel", methods=["POST"])
@blp.response(200, PurchaseOut)
@roles_required(*BUYERS)
def cancel_purchase(purchase_id):
    purchase = still_ordered(purchase_id)
    purchase.status = "cancelled"
    db.session.commit()
    return load(purchase_id)