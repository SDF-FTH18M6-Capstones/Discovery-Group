from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import fields, validate
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.audit import audit
from app.auth import is_role, roles_required
from app.crud import PageQuery, get_or_404, page_schema, paginate
from app.extensions import db
from app.models import Product, Sale, SaleItem
from app.models.sales import PAYMENT_METHODS, SALE_STATUSES
from app.notify import warn_if_low
from app.schemas import Schema
from app.shoptime import current_business, day_bounds, range_bounds, shop_today
from app.stockledger import move_stock

blp = Blueprint("sales", __name__, url_prefix="/api/sales", description="Sales (point of sale)")

SELLERS = ("admin", "sales")
money = {"places": 2, "as_string": True}
CENT = Decimal("0.01")


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
    idempotency_key = fields.String(load_default=None, validate=validate.Length(min=8, max=64))


class VoidIn(Schema):
    reason = fields.String(
        required=True,
        validate=validate.Length(
            min=3, max=500, error="Say why the sale is voided (3+ characters)."
        ),
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
    receipt_number = fields.String(attribute="reference")
    attendant_id = fields.Integer()
    attendant_name = fields.String(attribute="attendant.full_name")
    payment_method = fields.String()
    status = fields.String()
    total = fields.Decimal(**money)
    vat_rate = fields.Decimal(**money)
    vat_amount = fields.Decimal(**money)
    net_amount = fields.Method("get_net")
    created_at = fields.DateTime()
    voided_at = fields.DateTime(allow_none=True)
    voided_by_name = fields.String(attribute="voider.full_name", allow_none=True)
    void_reason = fields.String(allow_none=True)
    items = fields.List(fields.Nested(SaleLineOut))

    def get_net(self, sale):
        return f"{sale.total - sale.vat_amount:.2f}"


class SaleQuery(PageQuery):
    payment_method = fields.String(load_default=None, validate=validate.OneOf(PAYMENT_METHODS))
    status = fields.String(load_default=None, validate=validate.OneOf(SALE_STATUSES))
    day = fields.Date(load_default=None)
    date_from = fields.Date(load_default=None)
    date_to = fields.Date(load_default=None)
    attendant_id = fields.Integer(load_default=None)
    search = fields.String(load_default=None)  # receipt number, e.g. S-0012


def with_lines(query):
    return query.options(
        selectinload(Sale.items).selectinload(SaleItem.product),
        selectinload(Sale.attendant),
        selectinload(Sale.voider),
    )


def load(sale_id):
    return db.session.scalar(with_lines(db.select(Sale).where(Sale.id == sale_id)))


def vat_included(total, rate):
    if not rate:
        return Decimal("0.00")
    return (total * rate / (Decimal(100) + rate)).quantize(CENT, rounding=ROUND_HALF_UP)


@blp.route("/")
@blp.arguments(SaleQuery, location="query")
@blp.response(200, page_schema(SaleOut))
@roles_required(*SELLERS)
def list_sales(args):
    query = with_lines(db.select(Sale)).order_by(Sale.created_at.desc(), Sale.id.desc())
    if not is_role("admin"):
        query = query.where(Sale.attendant_id == current_user.id)
    elif args["attendant_id"]:
        query = query.where(Sale.attendant_id == args["attendant_id"])
    if args["payment_method"]:
        query = query.where(Sale.payment_method == args["payment_method"])
    if args["status"]:
        query = query.where(Sale.status == args["status"])
    if args["day"]:
        start, end = day_bounds(args["day"])
        query = query.where(Sale.created_at >= start, Sale.created_at < end)
    if args["date_from"] or args["date_to"]:
        start, end = range_bounds(
            args["date_from"] or args["date_to"], args["date_to"] or args["date_from"]
        )
        query = query.where(Sale.created_at >= start, Sale.created_at < end)
    if args["search"]:
        digits = args["search"].upper().removeprefix("S-").lstrip("0")
        query = (
            query.where(Sale.number == int(digits)) if digits.isdigit() else query.where(db.false())
        )
    return paginate(query, args["page"], args["per_page"])


def existing_sale(key):
    if not key:
        return None
    return db.session.scalar(db.select(Sale.id).where(Sale.idempotency_key == key))


@blp.route("/", methods=["POST"])
@blp.arguments(SaleIn)
@blp.response(201, SaleOut)
@roles_required(*SELLERS)
def create_sale(data):
    key = data["idempotency_key"]
    if (sale_id := existing_sale(key)) is not None:
        return load(sale_id)

    wanted = {}
    for line in data["items"]:
        wanted[line["product_id"]] = wanted.get(line["product_id"], 0) + line["quantity"]
    products = {
        p.id: p
        for p in db.session.scalars(
            db.select(Product)
            .where(Product.id.in_(wanted))
            .order_by(Product.id) 
            .with_for_update()
        )
    }
    missing = sorted(set(wanted) - set(products))
    if missing:
        db.session.rollback()
        abort(400, message=f"Product {missing[0]} does not exist")
    retired = [p.name for p in products.values() if not p.is_active]
    if retired:
        db.session.rollback()
        abort(409, message=f"No longer sold: {', '.join(retired)}.")
    short = [p for pid, p in products.items() if p.quantity < wanted[pid]]
    if short:
        db.session.rollback()
        names = ", ".join(f"{p.name} ({p.quantity} left)" for p in short)
        abort(409, message=f"Not enough stock: {names}.")

    rate = current_business().vat_rate
    sale = Sale(
        attendant_id=current_user.id,
        payment_method=data["payment_method"],
        total=0,
        vat_rate=rate,
        idempotency_key=key,
    )
    db.session.add(sale)
    db.session.flush()  
    total = Decimal("0")
    for product_id, quantity in wanted.items():
        product = products[product_id]
        sale.items.append(
            SaleItem(
                product_id=product_id,
                quantity=quantity,
                unit_price=product.selling_price,
                unit_cost=product.cost_price,
            )
        )
        total += product.selling_price * quantity
        before = product.quantity
        move_stock(product, -quantity, "sale", current_user.id, sale.reference, "Point of sale")
        warn_if_low(product, before)
    sale.total = total
    sale.vat_amount = vat_included(total, rate)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if (sale_id := existing_sale(key)) is not None:
            return load(sale_id)
        raise
    return load(sale.id)


@blp.route("/<int:sale_id>")
@blp.response(200, SaleOut)
@roles_required(*SELLERS)
def get_sale(sale_id):
    sale = get_or_404(Sale, sale_id)
    if not is_role("admin") and sale.attendant_id != current_user.id:
        abort(404, message=f"Sale {sale_id} not found")
    return load(sale_id)


@blp.route("/<int:sale_id>/void", methods=["POST"])
@blp.arguments(VoidIn)
@blp.response(200, SaleOut)
@roles_required("admin")
def void_sale(data, sale_id):
    sale = db.session.scalar(db.select(Sale).where(Sale.id == sale_id).with_for_update())
    if sale is None:
        abort(404, message=f"Sale {sale_id} not found")
    if sale.status == "voided":
        db.session.rollback()
        abort(409, message=f"{sale.reference} is already voided.")
    start, end = day_bounds(shop_today())
    if not start <= sale.created_at < end:
        db.session.rollback()
        abort(409, message="Only today's sales can be voided.")
    product_ids = sorted({line.product_id for line in sale.items})
    products = {
        p.id: p
        for p in db.session.scalars(
            db.select(Product)
            .where(Product.id.in_(product_ids))
            .order_by(Product.id)
            .with_for_update()
        )
    }
    for line in sale.items:
        move_stock(
            products[line.product_id],
            line.quantity,
            "sale_void",
            current_user.id,
            sale.reference,
            f"Void: {data['reason']}",
        )
    sale.status = "voided"
    sale.voided_by = current_user.id
    sale.voided_at = datetime.now(UTC)
    sale.void_reason = data["reason"]
    audit("voided", "sale", sale.id, f"{sale.reference} voided: {data['reason']}")
    db.session.commit()
    return load(sale_id)
