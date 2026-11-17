from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models import (
    ROLE_CLASSES,
    Asset,
    Category,
    Notification,
    Product,
    Purchase,
    PurchaseItem,
    Repair,
    Request,
    Sale,
    SaleItem,
    StockMovement,
    Supplier,
    User,
)

DEMO_PASSWORD = "ChangeMe123!"  # local demo data only

USERS = [
    ("admin", "David Nyongesa", "admin@stockpilot.test"),
    ("procurement", "Carlos Muchemi", "procurement@stockpilot.test"),
    ("inventory", "Keith Gachuche", "inventory@stockpilot.test"),
    ("sales", "Vincent Mutuma", "sales@stockpilot.test"),
    ("employee", "Barclay Koin", "employee@stockpilot.test"),
]

CATEGORIES = ["Beverages", "Grocery", "Packaging", "Stationery"]

PRODUCTS = [
    # sku, name, category, cost, price, quantity, reorder level
    ("SP-001", "Water Bottle 1L", "Beverages", "180.00", "250.00", 120, 20),
    ("SP-002", "Coffee Beans 250g", "Grocery", "480.00", "650.00", 14, 15),
    ("SP-003", "Kraft Bag Medium", "Packaging", "20.00", "35.00", 8, 25),
    ("SP-004", "Ziplock Bag 12x20", "Packaging", "10.00", "18.00", 65, 30),
    ("SP-005", "Mineral Water 500ml", "Beverages", "40.00", "60.00", 240, 48),
    ("SP-006", "A4 Printing Paper (ream)", "Stationery", "420.00", "550.00", 30, 10),
    ("SP-007", "Sugar 1kg", "Grocery", "150.00", "190.00", 0, 20),
    ("SP-008", "Paper Cups 8oz (50)", "Packaging", "90.00", "130.00", 40, 10),
]

SUPPLIERS = [
    ("Nairobi Packaging Supplies", "sales@nairobipack.example", "+254754381261"),
    ("Metro Wholesale", "orders@metro.example", "+254712758495"),
    ("Highland Coffee Traders", "hello@highland.example", "+254774658223"),
]

ASSETS = [
    ("AST-0001", "Dell Latitude 5440 laptop", "assigned", "employee@stockpilot.test"),
    ("AST-0002", "HP LaserJet printer", "available", None),
    ("AST-0003", "Office chair", "assigned", "sales@stockpilot.test"),
    ("AST-0004", "Barcode scanner", "in_repair", None),
]



SALES = [ 
    (6, "cash", [("SP-001", 2), ("SP-005", 4)]),
    (5, "mpesa", [("SP-002", 1), ("SP-008", 2)]),
    (4, "card", [("SP-006", 1), ("SP-001", 1)]),
    (3, "mpesa", [("SP-005", 6)]),
    (2, "cash", [("SP-004", 3), ("SP-003", 2)]),
    (2, "card", [("SP-007", 4)]),
    (1, "mpesa", [("SP-001", 3), ("SP-002", 1)]),
    (0, "cash", [("SP-001", 2), ("SP-002", 1), ("SP-003", 2)]),
]
RECEIVED_ORDER = ("Metro Wholesale", 5, [("SP-001", 24, "180.00"), ("SP-005", 48, "40.00")])
OPEN_ORDER = ("Highland Coffee Traders", 1, [("SP-002", 40, "480.00")])


def get_or_create(model, defaults=None, **lookup):
    item = db.session.scalar(db.select(model).filter_by(**lookup))
    if item is None:
        item = model(**lookup, **(defaults or {}))
        db.session.add(item)
        db.session.flush()
    return item


def seed():
    users = {}
    for role, name, email in USERS:
        user = db.session.scalar(db.select(User).filter_by(email=email))
        if user is None:
            user = ROLE_CLASSES[role](full_name=name, email=email)
            user.set_password(DEMO_PASSWORD)
            db.session.add(user)
            db.session.flush()
        else:
            user.full_name = name 
        users[email] = user

    categories = {name: get_or_create(Category, name=name) for name in CATEGORIES}

    for sku, name, category, cost, price, qty, reorder in PRODUCTS:
        get_or_create(
            Product,
            sku=sku,
            defaults={
                "name": name,
                "category_id": categories[category].id,
                "cost_price": Decimal(cost),
                "selling_price": Decimal(price),
                "quantity": qty,
                "reorder_level": reorder,
            },
        )

    for name, email, phone in SUPPLIERS:
        get_or_create(Supplier, name=name, defaults={"email": email, "phone": phone})

    for code, name, status, holder in ASSETS:
        holder_id = users[holder].id if holder else None
        get_or_create(
            Asset,
            asset_code=code,
            defaults={"name": name, "status": status, "assigned_to": holder_id},
        )

    employee = users["employee@stockpilot.test"]
    if not db.session.scalar(db.select(Request).filter_by(requester_id=employee.id)):
        db.session.add_all(
            [
                Request(
                    requester_id=employee.id,
                    item="Printer paper A4",
                    quantity=5,
                    urgency="normal",
                    reason="Monthly reports",
                ),
                Request(
                    requester_id=employee.id,
                    item="Laptop for new hire",
                    quantity=1,
                    urgency="urgent",
                    reason="New accounts assistant starts Monday",
                ),
            ]
        )

    if db.session.scalar(db.select(Sale.id).limit(1)) is None:
        add_history(users)

    db.session.commit()
    print(f"Seeded. Every demo user's password is {DEMO_PASSWORD}")


def add_history(users):
    now = datetime.now(UTC)
    ago = lambda days, hour=10: (now - timedelta(days=days)).replace(hour=hour, minute=15)
    products = {p.sku: p for p in db.session.scalars(db.select(Product))}
    suppliers = {s.name: s for s in db.session.scalars(db.select(Supplier))}
    keith = users["inventory@stockpilot.test"]
    carlos = users["procurement@stockpilot.test"]
    vincent = users["sales@stockpilot.test"]
    barclay = users["employee@stockpilot.test"]
    david = users["admin@stockpilot.test"]

    sold = {sku: 0 for sku in products}
    for _, _, lines in SALES:
        for sku, quantity in lines:
            sold[sku] += quantity
    received = {sku: 0 for sku in products}
    for sku, quantity, _ in RECEIVED_ORDER[2]:
        received[sku] += quantity

    for sku, product in products.items():
        opening = product.quantity + sold[sku] - received[sku]
        if opening:
            db.session.add(
                StockMovement(
                    product_id=product.id,
                    change=opening,
                    type="adjustment",
                    reason="Opening stock",
                    user_id=keith.id,
                    created_at=ago(8),
                )
            )

    for supplier_name, days, lines, status in [
        (*RECEIVED_ORDER, "received"),
        (*OPEN_ORDER, "ordered"),
    ]:
        order = Purchase(
            supplier_id=suppliers[supplier_name].id,
            created_by=carlos.id,
            status=status,
            total=sum(Decimal(cost) * qty for _, qty, cost in lines),
            created_at=ago(days + 2),
            updated_at=ago(days),
        )
        for sku, quantity, cost in lines:
            order.items.append(
                PurchaseItem(
                    product_id=products[sku].id, quantity=quantity, unit_cost=Decimal(cost)
                )
            )
        db.session.add(order)
        db.session.flush()
        if status == "received":
            for sku, quantity, _ in lines:
                db.session.add(
                    StockMovement(
                        product_id=products[sku].id,
                        change=quantity,
                        type="purchase",
                        reason=f"PO-{order.id:04d} received",
                        user_id=keith.id,
                        created_at=ago(days),
                    )
                )

    for i, (days, method, lines) in enumerate(SALES):
        when = ago(days, hour=9 + i % 8)
        sale = Sale(attendant_id=vincent.id, payment_method=method, total=0, created_at=when)
        for sku, quantity in lines:
            product = products[sku]
            sale.items.append(
                SaleItem(product_id=product.id, quantity=quantity, unit_price=product.selling_price)
            )
            sale.total += product.selling_price * quantity
            db.session.add(
                StockMovement(
                    product_id=product.id,
                    change=-quantity,
                    type="sale",
                    reason="Point of sale",
                    user_id=vincent.id,
                    created_at=when,
                )
            )
        db.session.add(sale)

    scanner = db.session.scalar(db.select(Asset).filter_by(asset_code="AST-0004"))
    if scanner:
        db.session.add(
            Repair(
                asset_id=scanner.id,
                reported_by=vincent.id,
                status="in_progress",
                description="Not reading shelf labels.",
            )
        )

    for user, message in [
        (david, "Sugar 1kg is out of stock."),
        (david, "Coffee Beans 250g is low on stock (14 left)."),
        (keith, "Kraft Bag Medium is low on stock (8 left)."),
        (carlos, f"Urgent request from {barclay.full_name}: Laptop for new hire × 1."),
        (carlos, "PO-0001 was received into stock."),
    ]:
        db.session.add(Notification(user_id=user.id, message=message))


if __name__ == "__main__":
    with create_app().app_context():
        seed()
