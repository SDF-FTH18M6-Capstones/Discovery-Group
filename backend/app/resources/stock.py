import csv
import io

from flask import Response
from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import fields, validate
from sqlalchemy.orm import selectinload

from app.auth import roles_required
from app.crud import PageQuery, page_schema, paginate
from app.extensions import db
from app.models import Product, StockMovement
from app.models.base import reference
from app.models.sales import MOVEMENT_TYPES
from app.notify import warn_if_low
from app.schemas import Schema
from app.shoptime import range_bounds, shop_zone
from app.stockledger import move_stock
from app.tenancy import current_business_id, next_number, scoped

blp = Blueprint("stock", __name__, url_prefix="/api/stock", description="Stock ledger")

STOCK = ("inventory",)
SEE_ALL = ("admin", "inventory")
CSV_LIMIT = 50_000


class MovementOut(Schema):
    id = fields.Integer()
    product_id = fields.Integer()
    product_name = fields.String(attribute="product.name")
    sku = fields.String(attribute="product.sku")
    change = fields.Integer()
    quantity_after = fields.Integer()
    type = fields.String()
    reference = fields.String(allow_none=True)
    reason = fields.String(allow_none=True)
    user_name = fields.String(attribute="user.full_name")
    balance_now = fields.Integer(attribute="product.quantity")
    created_at = fields.DateTime()


class MovementQuery(PageQuery):
    product_id = fields.Integer(load_default=None)
    type = fields.String(load_default=None, validate=validate.OneOf(MOVEMENT_TYPES))
    date_from = fields.Date(load_default=None)
    date_to = fields.Date(load_default=None)


class AdjustmentIn(Schema):
    product_id = fields.Integer(required=True)
    change = fields.Integer(
        required=True,
        validate=[
            validate.Range(min=-100000, max=100000),
            validate.NoneOf([0], error="Change must not be 0."),
        ],
    )
    reason = fields.String(
        required=True,
        validate=validate.Length(min=3, max=300, error="Give a reason (3+ characters)."),
    )


def movements(args):
    query = db.select(StockMovement).options(
        selectinload(StockMovement.product), selectinload(StockMovement.user)
    )
    if args["product_id"]:
        query = query.where(StockMovement.product_id == args["product_id"])
    if args["type"]:
        query = query.where(StockMovement.type == args["type"])
    if args["date_from"] or args["date_to"]:
        start, end = range_bounds(
            args["date_from"] or args["date_to"], args["date_to"] or args["date_from"]
        )
        query = query.where(StockMovement.created_at >= start, StockMovement.created_at < end)
    return query.order_by(StockMovement.created_at.desc(), StockMovement.id.desc())


@blp.route("/movements")
@blp.arguments(MovementQuery, location="query")
@blp.response(200, page_schema(MovementOut))
@roles_required(*SEE_ALL)
def list_movements(args):
    return paginate(movements(args), args["page"], args["per_page"])


@blp.route("/movements.csv")
@blp.arguments(MovementQuery, location="query")
@blp.response(200, content_type="text/csv")
@roles_required(*SEE_ALL)
def export_movements(args):
    zone = shop_zone()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        ["Date", "Product", "SKU", "Type", "Change", "Quantity after", "Reference", "Reason", "By"]
    )
    rows = db.session.scalars(scoped(movements(args)).limit(CSV_LIMIT))
    for m in rows:
        writer.writerow(
            [
                m.created_at.astimezone(zone).strftime("%Y-%m-%d %H:%M"),
                m.product.name,
                m.product.sku,
                m.type,
                m.change,
                m.quantity_after,
                m.reference or "",
                safe_cell(m.reason or ""),
                m.user.full_name,
            ]
        )
    return Response(
        out.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": 'attachment; filename="stock-ledger.csv"'},
    )


def safe_cell(text):
    return f"'{text}" if text[:1] in ("=", "+", "-", "@") else text


@blp.route("/adjustments", methods=["POST"])
@blp.arguments(AdjustmentIn)
@blp.response(201, MovementOut)
@roles_required(*STOCK)
def adjust(data):
    product = db.session.scalar(
        db.select(Product).where(Product.id == data["product_id"]).with_for_update()
    )
    if product is None:
        abort(400, message=f"Product {data['product_id']} does not exist")
    if product.quantity + data["change"] < 0:
        db.session.rollback()
        abort(409, message=f"Only {product.quantity} {product.name} in stock; cannot remove more.")
    before = product.quantity
    number = next_number(db.session.connection(), current_business_id(), "adjustment")
    movement = move_stock(
        product,
        data["change"],
        "adjustment",
        current_user.id,
        reference("ADJ", number),
        data["reason"],
    )
    warn_if_low(product, before, actor_id=current_user.id)
    db.session.commit()
    return movement
