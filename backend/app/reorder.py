from decimal import ROUND_HALF_UP, Decimal

from app.audit import audit
from app.extensions import db
from app.models import Product, Purchase, PurchaseItem, Supplier
from app.models.procurement import OPEN_PURCHASE_STATUSES

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


def draft_for_low_stock(product, actor_id):
    supplier = ordering_supplier(product)
    if supplier is None or already_on_order(product):
        return None
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
        purchase = Purchase(
            supplier_id=supplier.id,
            created_by=actor_id,
            status="draft",
            source="low_stock",
            total=0,
            notes="Prepared automatically because stock ran low. Check the quantities, "
            "then confirm the order.",
        )
        db.session.add(purchase)
        db.session.flush()
        audit("created", "purchase", purchase.id, f"{purchase.reference} drafted automatically")
    quantity = order_size(product)
    add_line(purchase, product, quantity)
    audit(
        "note",
        "purchase",
        purchase.id,
        f"{product.name} × {quantity} added automatically (low stock)",
    )
    return purchase


def draft_for_request(req, actor_id):
    if req.product_id is None:
        return None
    product = db.session.get(Product, req.product_id)
    supplier = ordering_supplier(product) if product else None
    if supplier is None:
        return None
    purchase = Purchase(
        supplier_id=supplier.id,
        created_by=actor_id,
        request_id=req.id,
        status="draft",
        source="request",
        total=0,
        notes=f"Prepared automatically from {req.reference}. Check it, then confirm the order.",
    )
    add_line(purchase, product, req.quantity)
    db.session.add(purchase)
    db.session.flush()
    audit("created", "purchase", purchase.id, f"{purchase.reference} drafted from {req.reference}")
    audit("linked", "request", req.id, f"Linked to {purchase.reference} (drafted automatically)")
    return purchase


def average_cost(product, quantity, unit_cost):
    on_hand = max(product.quantity, 0)
    if on_hand == 0:
        return Decimal(unit_cost).quantize(CENT)
    blended = (product.cost_price * on_hand + unit_cost * quantity) / (on_hand + quantity)
    return blended.quantize(CENT, rounding=ROUND_HALF_UP)
