from decimal import Decimal

from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import fields, validate
from sqlalchemy.orm import selectinload

from app.auth import is_role, roles_required
from app.crud import PageQuery, get_or_404, page_schema, paginate
from app.extensions import db
from app.models import Product, Sale, SaleItem, StockMovement
from app.models.sales import PAYMENT_METHODS
from app.notify import warn_if_low
from app.schemas import Schema
from app.shoptime import day_bounds

blp = Blueprint("sales", __name__, url_prefix="/api/sales", description="Sales (point of sale)")

SELLERS = ("admin", "sales")
money = {"places": 2, "as_string": True}


class SaleLineIn(Schema):
    product_id = fields.Integer(required=True)
    quantity = fields.Integer(required=True, validate=validate.Range(min=1, max=10000))


class SaleIn(Schema):
    payment_method = fields.String(required=True, validate=validate.OneOf(PAYMENT_METHODS))
    items = fields.List(
        fields.Nested(SaleLineIn),
        required=True,
        validate=validate.Length(min=1, max=100, error="Add at least one product."),
    )


class SaleLineOut(Schema):
    product_id = fields.Integer()
    product_name = fields.String(attribute="product.name")
    sku = fields.String(attribute="product.sku")
    quantity = fields.Integer()
    unit_price = fields.Decimal(**money)
    line_total = fields.Method("get_line_total")

    def get_line_total(self, line):
        return f"{line.unit_price * line.quantity:.2f}"


class SaleOut(Schema):
    id = fields.Integer()
    receipt_number = fields.Method("get_receipt")
    attendant_id = fields.Integer()
    attendant_name = fields.String(attribute="attendant.full_name")
    payment_method = fields.String()
    total = fields.Decimal(**money)
    created_at = fields.DateTime()
    items = fields.List(fields.Nested(SaleLineOut))

    def get_receipt(self, sale):
        return f"S-{sale.id:04d}"

class SaleQuery(PageQuery):
    payment_method = fields.String(load_default=None, validate=validate.OneOf(PAYMENT_METHODS))
    day = fields.Date(load_default=None)


def with_lines(query):
    return query.options(
        selectinload(Sale.items).selectinload(SaleItem.product), selectinload(Sale.attendant)
    )


@blp.route("/")
@blp.arguments(SaleQuery, location="query")
@blp.response(200, page_schema(SaleOut))
@roles_required(*SELLERS)
def list_sales(args):
    """Sales Attendants see their own sales; the Administrator sees everyone's."""
    query = with_lines(db.select(Sale)).order_by(Sale.created_at.desc(), Sale.id.desc())
    if not is_role("admin"):
        query = query.where(Sale.attendant_id == current_user.id)
    if args["payment_method"]:
        query = query.where(Sale.payment_method == args["payment_method"])
    if args["day"]:
        start, end = day_bounds(args["day"])  
        query = query.where(Sale.created_at >= start, Sale.created_at < end)
    return paginate(query, args["page"], args["per_page"])


@blp.route("/", methods=["POST"])
@blp.arguments(SaleIn)
@blp.response(201, SaleOut)
@roles_required(*SELLERS)
def create_sale(data):
    wanted = {}
    for line in data["items"]:  
        wanted[line["product_id"]] = wanted.get(line["product_id"], 0) + line["quantity"]
    products = {
        p.id: p
        for p in db.session.scalars(
            db.select(Product).where(Product.id.in_(wanted)).with_for_update()
        )
    }
    missing = sorted(set(wanted) - set(products))
    if missing:
        db.session.rollback()
        abort(400, message=f"Product {missing[0]} does not exist")
    short = [p for pid, p in products.items() if p.quantity < wanted[pid]]
    if short:
        db.session.rollback()
        names = ", ".join(f"{p.name} ({p.quantity} left)" for p in short)
        abort(409, message=f"Not enough stock: {names}.")

    sale = Sale(attendant_id=current_user.id, payment_method=data["payment_method"], total=0)
    total = Decimal("0")
    for product_id, quantity in wanted.items():
        product = products[product_id]
        sale.items.append(
            SaleItem(product_id=product_id, quantity=quantity, unit_price=product.selling_price)
        )
        total += product.selling_price * quantity
        product.quantity -= quantity
        db.session.add(
            StockMovement(
                product_id=product_id,
                change=-quantity,
                type="sale",
                reason="Point of sale",
                user_id=current_user.id,
            )
        )
        warn_if_low(product, actor_id=None)
    sale.total = total
    db.session.add(sale)
    db.session.commit()
    return db.session.scalar(with_lines(db.select(Sale).where(Sale.id == sale.id)))


@blp.route("/<int:sale_id>")
@blp.response(200, SaleOut)
@roles_required(*SELLERS)
def get_sale(sale_id):
    sale = get_or_404(Sale, sale_id)
    if not is_role("admin") and sale.attendant_id != current_user.id:
        abort(404, message=f"Sale {sale_id} not found")
    return sale
