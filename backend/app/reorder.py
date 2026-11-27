from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from app.audit import audit
from app.extensions import db
from app.mail import queue_email
from app.models import Business, Product, Purchase, PurchaseItem, Supplier
from app.models.procurement import OPEN_PURCHASE_STATUSES
from app.notify import notify_roles

CENT = Decimal("0.01")


def order_size(product):
    if product.reorder_quantity:
        return product.reorder_quantity
    return max(product.reorder_level * 2 - product.quantity, product.reorder_level, 1)


def already_on_order(product):
    return db.session.scalar(
        db.select(PurchaseItem.id)
        .join(Purchase)
        .where(
            PurchaseItem.product_id == product.id,
            Purchase.status.in_(OPEN_PURCHASE_STATUSES),
            PurchaseItem.received_quantity < PurchaseItem.quantity,
        )
        .limit(1)
    )


def ordering_supplier(product):
    if product.default_supplier_id is None or not product.is_active:
        return None
    supplier = db.session.get(Supplier, product.default_supplier_id)
    return supplier if supplier is not None and supplier.is_active else None


def add_line(purchase, product, quantity):
    purchase.items.append(
        PurchaseItem(
            product_id=product.id,
            quantity=quantity,
            unit_cost=product.cost_price,
            received_quantity=0,
        )
    )
    purchase.total = (purchase.total or 0) + product.cost_price * quantity


def email_supplier(purchase, supplier):
    if not supplier.email:
        return
    business = db.session.get(Business, purchase.business_id)
    lines = [
        f"Dear {supplier.name},",
        "",
        f"{business.name} would like to order the following ({purchase.reference}):",
        "",
    ]
    lines += [
        f"  {line.quantity} x {line.product.name} ({line.product.sku})" for line in purchase.items
    ]
    if business.address:
        lines += ["", f"Please deliver to: {business.address}"]
    contact = " or ".join(filter(None, (business.phone, business.email)))
    if contact:
        lines += [f"Questions about this order: {contact}"]
    lines += ["", "Thank you,", business.name]
    queue_email(
        supplier.email,
        f"Purchase order {purchase.reference} from {business.name}",
        "\n".join(lines),
    )


def place_order(purchase, actor_id=None, automatic=False):
    supplier = db.session.get(Supplier, purchase.supplier_id)
    purchase.status = "ordered"
    purchase.ordered_at = datetime.now(UTC)
    link = f"/purchases?open={purchase.id}"
    if automatic:
        sent = f"{purchase.reference} was sent to {supplier.name} automatically"
        notify_roles(("inventory",), f"{sent}; receive it when it arrives.", link=link)
        notify_roles(("procurement",), f"{sent} because stock ran low.", link=link)
        summary = sent
    else:
        notify_roles(
            ("inventory",),
            f"{purchase.reference} from {supplier.name} is on order; receive it when it arrives.",
            exclude=actor_id,
            link=link,
        )
        summary = f"{purchase.reference} placed"
    audit("ordered", "purchase", purchase.id, summary, {"status": ["draft", "ordered"]})
    email_supplier(purchase, supplier)


def draft_for_low_stock(product, actor_id):
    supplier = ordering_supplier(product)
    if supplier is None or already_on_order(product):
        return None
    if supplier.trusted:
        purchase = new_order(
            supplier, actor_id, "low_stock", "Sent automatically because stock ran low."
        )
        add_line(purchase, product, order_size(product))
        db.session.flush()
        place_order(purchase, actor_id, automatic=True)
        return purchase
    purchase = db.session.scalar(
        db.select(Purchase)
        .where(
            Purchase.status == "draft",
            Purchase.source == "low_stock",
            Purchase.supplier_id == supplier.id,
        )
        .order_by(Purchase.id.desc())
        .limit(1)
        .with_for_update()
    )
    if purchase is None:
        purchase = new_order(
            supplier,
            actor_id,
            "low_stock",
            "Prepared automatically because stock ran low. Check the quantities, then confirm "
            "the order.",
        )
    quantity = order_size(product)
    add_line(purchase, product, quantity)
    audit(
        "note",
        "purchase",
        purchase.id,
        f"{product.name} × {quantity} added automatically (low stock)",
    )
    return purchase


def new_order(supplier, actor_id, source, notes, request_id=None):
    purchase = Purchase(
        supplier_id=supplier.id,
        created_by=actor_id,
        request_id=request_id,
        status="draft",
        source=source,
        total=0,
        notes=notes,
    )
    db.session.add(purchase)
    db.session.flush()
    audit("created", "purchase", purchase.id, f"{purchase.reference} prepared automatically")
    return purchase


def draft_for_request(req, actor_id):
    if req.product_id is None:
        return None
    product = db.session.get(Product, req.product_id)
    supplier = ordering_supplier(product) if product else None
    if supplier is None:
        return None
    purchase = new_order(
        supplier,
        actor_id,
        "request",
        f"Prepared automatically from {req.reference}.",
        request_id=req.id,
    )
    add_line(purchase, product, req.quantity)
    db.session.flush()
    audit("linked", "request", req.id, f"Linked to {purchase.reference}")
    if supplier.trusted:
        place_order(purchase, actor_id, automatic=True)
    return purchase


def average_cost(product, quantity, unit_cost):
    on_hand = max(product.quantity, 0)
    if on_hand == 0:
        return Decimal(unit_cost).quantize(CENT)
    blended = (product.cost_price * on_hand + unit_cost * quantity) / (on_hand + quantity)
    return blended.quantize(CENT, rounding=ROUND_HALF_UP)
