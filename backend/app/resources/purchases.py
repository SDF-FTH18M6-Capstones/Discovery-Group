from datetime import UTC, datetime
from decimal import Decimal

from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import fields, validate
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.audit import audit
from app.auth import roles_required
from app.crud import PageQuery, find, get_or_404, page_schema, paginate
from app.extensions import db
from app.models import (
    GoodsReceipt,
    GoodsReceiptItem,
    Product,
    Purchase,
    PurchaseItem,
    Request,
    Supplier,
)
from app.models.procurement import OPEN_PURCHASE_STATUSES, PURCHASE_STATUSES
from app.notify import notify, notify_roles
from app.resources.requests import fulfil
from app.schemas import Schema
from app.stockledger import move_stock

blp = Blueprint("purchases", __name__, url_prefix="/api/purchases", description="Purchase orders")

BUYERS = ("admin", "procurement")
RECEIVERS = ("admin", "inventory")
VIEWERS = ("admin", "procurement", "inventory")
AWAITING = ("ordered", "partially_received")
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
    request_id = fields.Integer(allow_none=True, load_default=None)
    notes = fields.String(allow_none=True, load_default=None, validate=validate.Length(max=1000))
    confirm = fields.Boolean(load_default=False)


class CancelIn(Schema):
    reason = fields.String(
        required=True,
        validate=validate.Length(min=3, max=500, error="Say why the order is cancelled."),
    )


class ReceiveLineIn(Schema):
    item_id = fields.Integer(required=True)
    quantity = fields.Integer(required=True, validate=validate.Range(min=0, max=100000))


class ReceiveIn(Schema):

    lines = fields.List(fields.Nested(ReceiveLineIn), load_default=None)
    idempotency_key = fields.String(load_default=None, validate=validate.Length(min=8, max=64))
    note = fields.String(allow_none=True, load_default=None, validate=validate.Length(max=500))


class PurchaseLineOut(Schema):
    id = fields.Integer()
    product_id = fields.Integer()
    product_name = fields.String(attribute="product.name")
    sku = fields.String(attribute="product.sku")
    quantity = fields.Integer()
    received_quantity = fields.Integer()
    outstanding = fields.Integer()
    unit_cost = fields.Decimal(**money)


class ReceiptLineOut(Schema):
    product_id = fields.Integer()
    product_name = fields.String(attribute="product.name")
    quantity = fields.Integer()


class ReceiptOut(Schema):
    id = fields.Integer()
    reference = fields.String()
    purchase_id = fields.Integer()
    received_by_name = fields.String(attribute="receiver.full_name")
    note = fields.String(allow_none=True)
    created_at = fields.DateTime()
    items = fields.List(fields.Nested(ReceiptLineOut))


class PurchaseOut(Schema):
    id = fields.Integer()
    reference = fields.String()
    supplier_id = fields.Integer()
    supplier_name = fields.String(attribute="supplier.name")
    supplier_code = fields.String(attribute="supplier.code")
    created_by = fields.Integer()
    creator_name = fields.String(attribute="creator.full_name")
    request_id = fields.Integer(allow_none=True)
    request_reference = fields.String(attribute="request.reference", allow_none=True)
    status = fields.String()
    total = fields.Decimal(**money)
    notes = fields.String(allow_none=True)
    ordered_at = fields.DateTime(allow_none=True)
    received_at = fields.DateTime(allow_none=True)
    cancelled_at = fields.DateTime(allow_none=True)
    cancel_reason = fields.String(allow_none=True)
    created_at = fields.DateTime()
    updated_at = fields.DateTime()
    items = fields.List(fields.Nested(PurchaseLineOut))
    receipts = fields.List(fields.Nested(ReceiptOut))


class PurchaseQuery(PageQuery):
    status = fields.String(
        load_default=None, validate=validate.OneOf((*PURCHASE_STATUSES, "awaiting", "open"))
    )
    supplier_id = fields.Integer(load_default=None)
    search = fields.String(load_default=None)


def with_lines(query):
    return query.options(
        selectinload(Purchase.items).selectinload(PurchaseItem.product),
        selectinload(Purchase.supplier),
        selectinload(Purchase.creator),
        selectinload(Purchase.request),
        selectinload(Purchase.receipts)
        .selectinload(GoodsReceipt.items)
        .selectinload(GoodsReceiptItem.product),
        selectinload(Purchase.receipts).selectinload(GoodsReceipt.receiver),
    )


def load(purchase_id):
    get_or_404(Purchase, purchase_id)
    db.session.expire_all()
    return db.session.scalar(with_lines(db.select(Purchase).where(Purchase.id == purchase_id)))


@blp.route("/")
@blp.arguments(PurchaseQuery, location="query")
@blp.response(200, page_schema(PurchaseOut))
@roles_required(*VIEWERS)
def list_purchases(args):
    query = with_lines(db.select(Purchase)).order_by(Purchase.created_at.desc(), Purchase.id.desc())
    status = args["status"]
    if status == "awaiting":
        query = query.where(Purchase.status.in_(AWAITING))
    elif status == "open":
        query = query.where(Purchase.status.in_(OPEN_PURCHASE_STATUSES))
    elif status:
        query = query.where(Purchase.status == status)
    if args["supplier_id"]:
        query = query.where(Purchase.supplier_id == args["supplier_id"])
    if args["search"]:
        digits = args["search"].upper().removeprefix("PO-").lstrip("0")
        query = (
            query.where(Purchase.number == int(digits))
            if digits.isdigit()
            else query.where(db.false())
        )
    return paginate(query, args["page"], args["per_page"])


def check_order(data):
    supplier = find(Supplier, data["supplier_id"])
    if supplier is None:
        abort(400, message=f"Supplier {data['supplier_id']} does not exist")
    if not supplier.is_active:
        abort(409, message=f"{supplier.name} is inactive and cannot receive new orders.")
    product_ids = {line["product_id"] for line in data["items"]}
    products = db.session.scalars(db.select(Product).where(Product.id.in_(product_ids))).all()
    found = {p.id for p in products}
    if product_ids - found:
        abort(400, message=f"Product {sorted(product_ids - found)[0]} does not exist")
    retired = [p.name for p in products if not p.is_active]
    if retired:
        abort(409, message=f"Retired products cannot be ordered: {', '.join(retired)}.")
    if data["request_id"] is not None:
        req = find(Request, data["request_id"])
        if req is None:
            abort(400, message=f"Request {data['request_id']} does not exist")
        if req.status != "approved":
            abort(
                409,
                message=f"Only approved requests can be linked ({req.reference} is {req.status}).",
            )
        return req
    return None


def fill_lines(purchase, items):
    purchase.items.clear()
    total = Decimal("0")
    for line in items:
        purchase.items.append(PurchaseItem(**line, received_quantity=0))
        total += line["unit_cost"] * line["quantity"]
    purchase.total = total


def place_order(purchase):
    purchase.status = "ordered"
    purchase.ordered_at = datetime.now(UTC)
    notify_roles(
        RECEIVERS,
        f"{purchase.reference} from {db.session.get(Supplier, purchase.supplier_id).name} is on "
        "order; receive it when it arrives.",
        exclude=current_user.id,
        link=f"/purchases?open={purchase.id}",
    )
    audit(
        "ordered",
        "purchase",
        purchase.id,
        f"{purchase.reference} placed",
        {"status": ["draft", "ordered"]},
    )


def link_request(purchase, req):
    if req is not None and purchase.request_id != req.id:
        purchase.request_id = req.id
        audit("linked", "request", req.id, f"Linked to {purchase.reference}")


@blp.route("/", methods=["POST"])
@blp.arguments(PurchaseIn)
@blp.response(201, PurchaseOut)
@roles_required(*BUYERS)
def create_purchase(data):
    req = check_order(data)
    purchase = Purchase(
        supplier_id=data["supplier_id"],
        created_by=current_user.id,
        notes=data["notes"],
        status="draft",
        total=0,
    )
    fill_lines(purchase, data["items"])
    db.session.add(purchase)
    db.session.flush()
    audit("created", "purchase", purchase.id, f"{purchase.reference} drafted")
    link_request(purchase, req)
    if data["confirm"]:
        place_order(purchase)
    db.session.commit()
    return load(purchase.id)


def locked(purchase_id):
    purchase = db.session.scalar(
        db.select(Purchase).where(Purchase.id == purchase_id).with_for_update()
    )
    if purchase is None:
        abort(404, message=f"Purchase {purchase_id} not found")
    return purchase


def refuse(message):
    db.session.rollback()
    abort(409, message=message)


@blp.route("/<int:purchase_id>")
@blp.response(200, PurchaseOut)
@roles_required(*VIEWERS)
def get_purchase(purchase_id):
    return load(purchase_id)


@blp.route("/<int:purchase_id>", methods=["PUT"])
@blp.arguments(PurchaseIn)
@blp.response(200, PurchaseOut)
@roles_required(*BUYERS)
def update_purchase(data, purchase_id):
    purchase = locked(purchase_id)
    if purchase.status != "draft":
        refuse(f"Only draft orders can be edited; this one is {purchase.status}.")
    req = check_order(data)
    purchase.supplier_id = data["supplier_id"]
    purchase.notes = data["notes"]
    fill_lines(purchase, data["items"])
    link_request(purchase, req)
    if data["confirm"]:
        db.session.flush()
        place_order(purchase)
    db.session.commit()
    return load(purchase_id)


@blp.route("/<int:purchase_id>/confirm", methods=["POST"])
@blp.response(200, PurchaseOut)
@roles_required(*BUYERS)
def confirm_purchase(purchase_id):
    purchase = locked(purchase_id)
    if purchase.status != "draft":
        refuse(f"This order is already {purchase.status.replace('_', ' ')}.")
    supplier = db.session.get(Supplier, purchase.supplier_id)
    if not supplier.is_active:
        refuse(f"{supplier.name} is inactive and cannot receive new orders.")
    place_order(purchase)
    db.session.commit()
    return load(purchase_id)


@blp.route("/<int:purchase_id>/cancel", methods=["POST"])
@blp.arguments(CancelIn)
@blp.response(200, PurchaseOut)
@roles_required(*BUYERS)
def cancel_purchase(data, purchase_id):
    purchase = locked(purchase_id)
    if purchase.status not in ("draft", "ordered"):
        refuse(f"This order is already {purchase.status.replace('_', ' ')}.")
    old = purchase.status
    purchase.status = "cancelled"
    purchase.cancelled_at = datetime.now(UTC)
    purchase.cancel_reason = data["reason"]
    audit(
        "cancelled",
        "purchase",
        purchase.id,
        f"{purchase.reference} cancelled: {data['reason']}",
        {"status": [old, "cancelled"]},
    )
    if purchase.request_id:
        audit("note", "request", purchase.request_id, f"{purchase.reference} was cancelled")
    db.session.commit()
    return load(purchase_id)


def existing_receipt(key):
    if not key:
        return None
    return db.session.scalar(db.select(GoodsReceipt).where(GoodsReceipt.idempotency_key == key))


@blp.route("/<int:purchase_id>/receive", methods=["POST"])
@blp.arguments(ReceiveIn)
@blp.response(200, PurchaseOut)
@roles_required(*RECEIVERS)
def receive_purchase(data, purchase_id): 
    previous = existing_receipt(data["idempotency_key"])
    if previous is not None:
        if previous.purchase_id != purchase_id:
            abort(409, message="This idempotency key was used for another order.")
        return load(purchase_id)

    purchase = locked(purchase_id)
    if purchase.status not in AWAITING:
        if purchase.status == "draft":
            refuse("Confirm this order before receiving it.")
        refuse(f"This order is already {purchase.status.replace('_', ' ')}.")

    lines = {line.id: line for line in purchase.items}
    if data["lines"] is None:
        wanted = {line.id: line.outstanding for line in purchase.items if line.outstanding}
    else:
        wanted = {}
        for entry in data["lines"]:
            if entry["item_id"] not in lines:
                refuse(f"Line {entry['item_id']} is not on {purchase.reference}.")
            if entry["quantity"]:
                wanted[entry["item_id"]] = wanted.get(entry["item_id"], 0) + entry["quantity"]
    if not wanted:
        refuse("Enter how many of at least one product arrived.")
    over = [
        f"{lines[i].product.name} (only {lines[i].outstanding} outstanding)"
        for i, qty in wanted.items()
        if qty > lines[i].outstanding
    ]
    if over:
        refuse(f"More than ordered: {', '.join(over)}.")

    receipt = GoodsReceipt(
        purchase_id=purchase.id,
        received_by=current_user.id,
        idempotency_key=data["idempotency_key"],
        note=data["note"],
    )
    db.session.add(receipt)
    db.session.flush()
    product_ids = sorted({lines[i].product_id for i in wanted})
    products = {
        p.id: p
        for p in db.session.scalars(
            db.select(Product)
            .where(Product.id.in_(product_ids))
            .order_by(Product.id)
            .with_for_update()
        )
    }
    for item_id, quantity in wanted.items():
        line = lines[item_id]
        line.received_quantity += quantity
        receipt.items.append(
            GoodsReceiptItem(
                purchase_item_id=line.id, product_id=line.product_id, quantity=quantity
            )
        )
        move_stock(
            products[line.product_id],
            quantity,
            "purchase",
            current_user.id,
            receipt.reference,
            f"{purchase.reference} received",
        )

    complete = all(line.outstanding == 0 for line in purchase.items)
    old = purchase.status
    purchase.status = "received" if complete else "partially_received"
    if complete:
        purchase.received_at = datetime.now(UTC)
    word = "received in full" if complete else "partly received"
    audit(
        "received",
        "purchase",
        purchase.id,
        f"{receipt.reference}: {purchase.reference} {word}",
        {"status": [old, purchase.status]} if old != purchase.status else None,
    )
    notify(
        [purchase.created_by],
        f"{purchase.reference} was {word} ({receipt.reference}).",
        link=f"/purchases?open={purchase.id}",
    )
    if purchase.request_id:
        req = db.session.get(Request, purchase.request_id)
        audit("note", "request", req.id, f"{receipt.reference}: {purchase.reference} {word}")
        if complete:
            fulfil(req, f"Fulfilled: {purchase.reference} received")
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if existing_receipt(data["idempotency_key"]) is not None:
            return load(purchase_id) 
        raise
    return load(purchase_id)
