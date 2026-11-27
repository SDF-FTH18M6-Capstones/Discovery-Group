from datetime import UTC, datetime
from decimal import Decimal

from flask import current_app, request
from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import fields, validate

from app.audit import audit
from app.auth import can, roles_required
from app.extensions import db
from app.models import GoodsReceipt, GoodsReceiptItem, Product, Purchase, PurchaseItem, Supplier
from app.receipts import ReaderError, best_match, parse_receipt_text, read_with_ai
from app.reorder import average_cost
from app.schemas import Schema
from app.stockledger import move_stock

blp = Blueprint("receipts", __name__, url_prefix="/api/receipts", description="Receipt scanning")

READERS = ("admin", "procurement", "inventory")
STOCKERS = ("procurement", "inventory")
PHOTO_TYPES = ("image/jpeg", "image/png", "image/webp")
MAX_PHOTO_BYTES = 8 * 1024 * 1024
money = {"places": 2, "as_string": True, "allow_none": True}


class ReaderOut(Schema):
    mode = fields.String()
    can_expense = fields.Boolean()
    can_stock = fields.Boolean()


class TextIn(Schema):
    text = fields.String(
        required=True,
        validate=validate.Length(min=10, max=20_000, error="No writing was found on the photo."),
    )


class ProductOut(Schema):
    id = fields.Integer()
    name = fields.String()
    sku = fields.String()
    quantity = fields.Integer()


class ItemOut(Schema):
    description = fields.String()
    quantity = fields.Decimal(as_string=True)
    unit_price = fields.Decimal(**money)
    amount = fields.Decimal(**money)
    product_id = fields.Integer(allow_none=True)
    product = fields.Nested(ProductOut, allow_none=True)


class ReadingOut(Schema):
    supplier = fields.String()
    supplier_id = fields.Integer(allow_none=True)
    date = fields.Date(allow_none=True)
    number = fields.String(allow_none=True)
    total = fields.Decimal(**money)
    tax = fields.Decimal(**money)
    items = fields.List(fields.Nested(ItemOut))


class StockLineIn(Schema):
    product_id = fields.Integer(required=True)
    quantity = fields.Integer(required=True, validate=validate.Range(min=1, max=100000))
    unit_cost = fields.Decimal(required=True, places=2, validate=validate.Range(min=0))


class StockIn(Schema):
    supplier_id = fields.Integer(allow_none=True, load_default=None)
    supplier_name = fields.String(
        allow_none=True, load_default=None, validate=validate.Length(max=150)
    )
    number = fields.String(allow_none=True, load_default=None, validate=validate.Length(max=40))
    lines = fields.List(
        fields.Nested(StockLineIn),
        required=True,
        validate=validate.Length(min=1, max=100, error="Add at least one product."),
    )


class StockOut(Schema):
    purchase_id = fields.Integer()
    reference = fields.String()
    receipt_reference = fields.String()
    total = fields.Decimal(places=2, as_string=True)


def matched(reading):
    products = {p.id: p for p in db.session.scalars(db.select(Product).where(Product.is_active))}
    by_sku = {p.sku.lower(): p.id for p in products.values() if p.sku}
    names = [(p.id, p.name) for p in products.values()]
    for item in reading["items"]:
        words = item["description"].lower().split()
        item["product_id"] = next((by_sku[w] for w in words if w in by_sku), None) or best_match(
            item["description"], names
        )
        item["product"] = products.get(item["product_id"])
    suppliers = db.session.execute(
        db.select(Supplier.id, Supplier.name).where(Supplier.is_active)
    ).all()
    reading["supplier_id"] = best_match(reading["supplier"], suppliers, 0.7)
    return reading


@blp.route("/reader")
@blp.response(200, ReaderOut)
@roles_required(*READERS)
def reader():
    return {
        "mode": "ai" if current_app.config["RECEIPT_AI_KEY"] else "device",
        "can_expense": can("admin"),
        "can_stock": can(*STOCKERS),
    }


@blp.route("/text", methods=["POST"])
@blp.arguments(TextIn)
@blp.response(200, ReadingOut)
@roles_required(*READERS)
def read_text(data):
    return matched(parse_receipt_text(data["text"]))


@blp.route("/photo", methods=["POST"])
@blp.response(200, ReadingOut)
@roles_required(*READERS)
def read_photo():
    config = current_app.config
    if not config["RECEIPT_AI_KEY"]:
        abort(409, message="Online reading is not set up. The photo is read on this device.")
    photo = request.files.get("photo")
    if photo is None or not photo.filename:
        abort(400, message="Take or choose a photo of the receipt.")
    if photo.mimetype not in PHOTO_TYPES:
        abort(422, message="Use a JPEG, PNG or WebP photo.")
    image = photo.read(MAX_PHOTO_BYTES + 1)
    if len(image) > MAX_PHOTO_BYTES:
        abort(413, message="That photo is too large. Use one under 8 MB.")
    try:
        reading = read_with_ai(image, photo.mimetype, config)
    except ReaderError as err:
        abort(502, message=str(err))
    return matched(reading)


def supplier_for(data):
    if data["supplier_id"] is not None:
        supplier = db.session.get(Supplier, data["supplier_id"])
        if supplier is None:
            abort(400, message=f"Supplier {data['supplier_id']} does not exist")
        return supplier
    name = (data["supplier_name"] or "").strip()
    if len(name) < 2:
        abort(422, message="Say who sold you the goods.")
    supplier = db.session.scalar(
        db.select(Supplier).where(db.func.lower(Supplier.name) == name.lower())
    )
    if supplier is None:
        supplier = Supplier(name=name)
        db.session.add(supplier)
        db.session.flush()
        audit("created", "supplier", supplier.id, f"{name} added from a scanned receipt")
    return supplier


@blp.route("/stock", methods=["POST"])
@blp.arguments(StockIn)
@blp.response(201, StockOut)
@roles_required(*STOCKERS)
def record_stock(data):
    supplier = supplier_for(data)
    wanted = {}
    for line in data["lines"]:
        quantity, cost = wanted.get(line["product_id"], (0, Decimal(0)))
        wanted[line["product_id"]] = (
            quantity + line["quantity"],
            cost + line["unit_cost"] * line["quantity"],
        )
    products = {
        p.id: p
        for p in db.session.scalars(
            db.select(Product)
            .where(Product.id.in_(sorted(wanted)))
            .order_by(Product.id)
            .with_for_update()
        )
    }
    missing = sorted(set(wanted) - set(products))
    if missing:
        abort(400, message=f"Product {missing[0]} does not exist")
    retired = [p.name for p in products.values() if not p.is_active]
    if retired:
        abort(409, message=f"Retired products cannot be stocked: {', '.join(retired)}.")

    now = datetime.now(UTC)
    note = f"Bought over the counter, receipt {data['number']}" if data["number"] else None
    purchase = Purchase(
        supplier_id=supplier.id,
        created_by=current_user.id,
        source="receipt",
        status="received",
        notes=note or "Bought over the counter",
        ordered_at=now,
        received_at=now,
        total=0,
    )
    db.session.add(purchase)
    for product_id, (quantity, cost) in wanted.items():
        unit_cost = (cost / quantity).quantize(Decimal("0.01"))
        purchase.items.append(
            PurchaseItem(
                product_id=product_id,
                quantity=quantity,
                unit_cost=unit_cost,
                received_quantity=quantity,
            )
        )
        purchase.total += unit_cost * quantity
    receipt = GoodsReceipt(purchase=purchase, received_by=current_user.id, note=note)
    db.session.add(receipt)
    db.session.flush()
    for line in purchase.items:
        product = products[line.product_id]
        new_cost = average_cost(product, line.quantity, line.unit_cost)
        if new_cost != product.cost_price:
            audit(
                "updated",
                "product",
                product.id,
                f"{product.name}: cost price {product.cost_price:.2f} → {new_cost:.2f} "
                f"(average after {receipt.reference})",
                {"cost_price": [f"{product.cost_price:.2f}", f"{new_cost:.2f}"]},
            )
            product.cost_price = new_cost
        receipt.items.append(
            GoodsReceiptItem(
                purchase_item_id=line.id, product_id=product.id, quantity=line.quantity
            )
        )
        move_stock(
            product,
            line.quantity,
            "purchase",
            current_user.id,
            receipt.reference,
            f"{purchase.reference} bought from {supplier.name}",
        )
    audit(
        "received",
        "purchase",
        purchase.id,
        f"{receipt.reference}: {purchase.reference} bought from {supplier.name} and received",
    )
    db.session.commit()
    return {
        "purchase_id": purchase.id,
        "reference": purchase.reference,
        "receipt_reference": receipt.reference,
        "total": purchase.total,
    }
