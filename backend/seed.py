"""Fills the database with demo data. Run from the backend folder:  python seed.py
Safe to run more than once: existing rows are left alone.
"""

from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models import ROLE_CLASSES, Asset, Category, Product, Request, Supplier, User

DEMO_PASSWORD = "ChangeMe123!"  # local demo data only

USERS = [
    ("admin", "Ada Wekesa", "admin@stockpilot.test"),
    ("procurement", "Jane Otieno", "procurement@stockpilot.test"),
    ("inventory", "Brian Mwangi", "inventory@stockpilot.test"),
    ("sales", "Pauline Wanjiku", "sales@stockpilot.test"),
    ("employee", "Alex Kamau", "employee@stockpilot.test"),
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
    ("Nairobi Packaging Supplies", "sales@nairobipack.example", "+254700000001"),
    ("Metro Wholesale", "orders@metro.example", "+254700000002"),
    ("Highland Coffee Traders", "hello@highland.example", "+254700000003"),
]

ASSETS = [
    ("AST-0001", "Dell Latitude 5440 laptop", "assigned", "employee@stockpilot.test"),
    ("AST-0002", "HP LaserJet printer", "available", None),
    ("AST-0003", "Office chair", "assigned", "sales@stockpilot.test"),
    ("AST-0004", "Barcode scanner", "in_repair", None),
]


def get_or_create(model, defaults=None, **lookup):
    item = db.session.scalar(db.select(model).filter_by(**lookup))
    if item is None:
        item = model(**lookup, **(defaults or {}))
        db.session.add(item)
        db.session.flush()
    return item


def seed():
    """Insert demo users, categories, products, suppliers, assets and requests."""
    users = {}
    for role, name, email in USERS:
        user = db.session.scalar(db.select(User).filter_by(email=email))
        if user is None:
            user = ROLE_CLASSES[role](full_name=name, email=email)
            user.set_password(DEMO_PASSWORD)
            db.session.add(user)
            db.session.flush()
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

    db.session.commit()
    print(f"Seeded. Every demo user's password is {DEMO_PASSWORD}")


if __name__ == "__main__":
    with create_app().app_context():
        seed()