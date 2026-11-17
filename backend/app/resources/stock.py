from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import fields, validate
from sqlalchemy.orm import selectinload

from app.auth import roles_required
from app.crud import PageQuery, page_schema, paginate
from app.extensions import db
from app.models import Product, StockMovement
from app.models.sales import MOVEMENT_TYPES
from app.notify import warn_if_low
from app.schemas import Schema

blp = Blueprint("stock", __name__, url_prefix="/api/stock", description="Stock ledger")

STOCK = ("admin", "inventory")


class MovementOut(Schema):
    id = fields.Integer()
    product_id = fields.Integer()
    product_name = fields.String(attribute="product.name")
    sku = fields.String(attribute="product.sku")
    change = fields.Integer()
    type = fields.String()
    reason = fields.String()
    user_name = fields.String(attribute="user.full_name")
    balance_now = fields.Integer(attribute="product.quantity")
    created_at = fields.DateTime()


class MovementQuery(PageQuery):
    product_id = fields.Integer(load_default=None)
    type = fields.String(load_default=None, validate=validate.OneOf(MOVEMENT_TYPES))


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


@blp.route("/movements")
@blp.arguments(MovementQuery, location="query")
@blp.response(200, page_schema(MovementOut))
@roles_required(*STOCK)
def list_movements(args):
    query = (
        db.select(StockMovement)
        .options(selectinload(StockMovement.product), selectinload(StockMovement.user))
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
    )
    if args["product_id"]:
        query = query.where(StockMovement.product_id == args["product_id"])
    if args["type"]:
        query = query.where(StockMovement.type == args["type"])
    return paginate(query, args["page"], args["per_page"])


@blp.route("/adjustments", methods=["POST"])
@blp.arguments(AdjustmentIn)
@blp.response(201, MovementOut)
@roles_required(*STOCK)
def adjust(data):
    """Count correction, damage, theft… Stock can never go below zero."""
    product = db.session.scalar(
        db.select(Product).where(Product.id == data["product_id"]).with_for_update()
    )
    if product is None:
        abort(400, message=f"Product {data['product_id']} does not exist")
    if product.quantity + data["change"] < 0:
        db.session.rollback()
        abort(409, message=f"Only {product.quantity} {product.name} in stock; cannot remove more.")
    product.quantity += data["change"]
    movement = StockMovement(
        product_id=product.id,
        change=data["change"],
        type="adjustment",
        reason=data["reason"],
        user_id=current_user.id,
    )
    db.session.add(movement)
    warn_if_low(product, actor_id=current_user.id)
    db.session.commit()
    return movement