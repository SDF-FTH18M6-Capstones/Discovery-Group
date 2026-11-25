from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models import (
    ROLE_CLASSES,
    Asset,
    AssetAssignment,
    AssetCategory,
    AuditLog,
    Business,
    Category,
    Expense,
    GoodsReceipt,
    GoodsReceiptItem,
    Notification,
    Product,
    Purchase,
    PurchaseItem,
    Repair,
    Request,
    Sale,
    SaleItem,
    Supplier,
    User,
)
from app.models.base import reference
from app.resources.sales import vat_included
from app.stockledger import move_stock
from app.tenancy import tenant

DEMO_PASSWORD = "ChangeMe123!"

DEMO_SHOP = {
    "name": "StockPilot Demo Shop",
    "join_code": "DEMO2026",
    "phone": "+254 700 000 000",
    "address": "Moi Avenue, Nairobi",
    "receipt_footer": "Thank you for shopping with us!",
    "users": [
        ("admin", "David Nyongesa", "admin@stockpilot.test"),
        ("procurement", "Carlos Muchemi", "procurement@stockpilot.test"),
        ("inventory", "Keith Gachuche", "inventory@stockpilot.test"),
        ("sales", "Vincent Mutuma", "sales@stockpilot.test"),
        ("employee", "Barclay Koin", "employee@stockpilot.test"),
    ],
    "categories": ["Beverages", "Grocery", "Packaging", "Stationery"],
    "products": [
        ("SP-001", "Water Bottle 1L", "Beverages", "180.00", "250.00", 120, 20),
        ("SP-002", "Coffee Beans 250g", "Grocery", "480.00", "650.00", 30, 15),
        ("SP-003", "Kraft Bag Medium", "Packaging", "20.00", "35.00", 12, 25),
        ("SP-004", "Ziplock Bag 12x20", "Packaging", "10.00", "18.00", 70, 30),
        ("SP-005", "Mineral Water 500ml", "Beverages", "40.00", "60.00", 200, 48),
        ("SP-006", "A4 Printing Paper (ream)", "Stationery", "420.00", "550.00", 31, 10),
        ("SP-007", "Sugar 1kg", "Grocery", "150.00", "190.00", 8, 20),
        ("SP-008", "Paper Cups 8oz (50)", "Packaging", "90.00", "130.00", 42, 10),
    ],
    "suppliers": [
        ("Nairobi Packaging Supplies", "sales@nairobipack.example", "+254754381261"),
        ("Metro Wholesale", "orders@metro.example", "+254712758495"),
        ("Highland Coffee Traders", "hello@highland.example", "+254774658223"),
    ],
    "asset_categories": ["Computers", "Furniture", "Devices"],
    "assets": [
        (
            "Dell Latitude 5440 laptop",
            "Computers",
            "DL5440-88213",
            "employee@stockpilot.test",
            "good",
        ),
        ("HP LaserJet printer", "Devices", "HPLJ-55102", None, "good"),
        ("Office chair", "Furniture", None, "sales@stockpilot.test", "fair"),
        ("Barcode scanner", "Devices", "ZB-DS2208-1", "sales@stockpilot.test", "good"),
    ],
    "sales": [
        (6, "cash", [("SP-001", 2), ("SP-005", 4)]),
        (5, "mpesa", [("SP-002", 1), ("SP-008", 2)]),
        (4, "card", [("SP-006", 1), ("SP-001", 1)]),
        (3, "mpesa", [("SP-005", 6)]),
        (2, "cash", [("SP-004", 3), ("SP-003", 2)]),
        (2, "card", [("SP-007", 4)]),
        (1, "mpesa", [("SP-001", 3), ("SP-002", 1)]),
        (0, "cash", [("SP-001", 2), ("SP-002", 1), ("SP-003", 2)]),
    ],
    "expenses": [
        (20, "Rent", "Shop rent", "35000.00"),
        (3, "Electricity", "KPLC tokens", "4200.00"),
    ],
}

SECOND_SHOP = {
    "name": "Highland Café",
    "join_code": "CAFE2026",
    "timezone": "Africa/Nairobi",
    "users": [
        ("admin", "Amina Wanjiru", "owner@highlandcafe.test"),
        ("sales", "Brian Otieno", "till@highlandcafe.test"),
    ],
    "categories": ["Hot drinks", "Pastries"],
    "products": [
        ("HC-01", "Cappuccino", "Hot drinks", "80.00", "250.00", 200, 20),
        ("HC-02", "Masala chai", "Hot drinks", "30.00", "120.00", 300, 30),
        ("HC-03", "Croissant", "Pastries", "60.00", "180.00", 12, 15),
    ],
    "suppliers": [("Nairobi Bakers", "orders@bakers.example", "+254711000111")],
    "asset_categories": ["Kitchen"],
    "assets": [("Espresso machine", "Kitchen", "LM-2020-77", None, "good")],
    "sales": [(1, "mpesa", [("HC-01", 3), ("HC-03", 2)]), (0, "cash", [("HC-02", 4)])],
    "expenses": [],
}


def ago(days, hour=10):
    return (datetime.now(UTC) - timedelta(days=days)).replace(hour=hour, minute=15)


def seed_business(spec):
    business = db.session.scalar(db.select(Business).filter_by(join_code=spec["join_code"]))
    if business is not None:
        print(f"  {spec['name']}: already there, skipped")
        return
    business = Business(
        name=spec["name"],
        join_code=spec["join_code"],
        phone=spec.get("phone"),
        address=spec.get("address"),
        receipt_footer=spec.get("receipt_footer"),
    )
    db.session.add(business)
    db.session.flush()

    with tenant(business.id):
        users = {}
        for role, name, email in spec["users"]:
            if db.session.scalar(db.select(User.id).filter_by(email=email)):
                raise SystemExit(
                    f"{email} already belongs to another business; use a fresh database."
                )
            user = ROLE_CLASSES[role](
                full_name=name, email=email, email_verified_at=datetime.now(UTC)
            )
            user.set_password(DEMO_PASSWORD)
            db.session.add(user)
            users[email] = user
        db.session.flush()
        by_role = {u.role: u for u in users.values()}
        admin = by_role["admin"]
        stock_keeper = by_role.get("inventory", admin)
        buyer = by_role.get("procurement", admin)
        seller = by_role.get("sales", admin)

        categories = {name: Category(name=name) for name in spec["categories"]}
        db.session.add_all(categories.values())
        db.session.flush()

        products = {}
        for sku, name, category, cost, price, opening, reorder in spec["products"]:
            product = Product(
                sku=sku,
                name=name,
                category_id=categories[category].id,
                cost_price=Decimal(cost),
                selling_price=Decimal(price),
                quantity=0,
                reorder_level=reorder,
            )
            db.session.add(product)
            db.session.flush()
            audit_at(
                admin, "created", "product", product.id, f"Product {sku} {name} created", ago(9)
            )
            opening_line = move_stock(
                product, opening, "adjustment", stock_keeper.id, None, "Opening stock"
            )
            opening_line.created_at = ago(9)
            products[sku] = product
        db.session.flush()

        suppliers = [
            Supplier(name=name, email=email, phone=phone)
            for name, email, phone in spec["suppliers"]
        ]
        db.session.add_all(suppliers)
        db.session.flush()

        add_purchases(spec, products, suppliers, buyer, stock_keeper)
        add_sales(spec, products, seller, business.vat_rate)
        add_assets(spec, users, admin, stock_keeper)
        add_requests_and_notes(users, by_role, admin)
        for days, category, description, amount in spec["expenses"]:
            db.session.add(
                Expense(
                    spent_on=date.today() - timedelta(days=days),
                    category=category,
                    description=description,
                    amount=Decimal(amount),
                    created_by=admin.id,
                )
            )
        db.session.commit()
    print(f"  {spec['name']}: join code {spec['join_code']}, {len(spec['users'])} users")


def audit_at(user, action, entity, entity_id, summary, when, changes=None):
    db.session.add(
        AuditLog(
            user_id=user.id,
            action=action,
            entity_type=entity,
            entity_id=entity_id,
            summary=summary,
            changes=changes,
            created_at=when,
        )
    )


def add_purchases(spec, products, suppliers, buyer, stock_keeper):
    if not spec["suppliers"] or len(products) < 2:
        return
    skus = list(products)
    received = Purchase(
        supplier_id=suppliers[min(1, len(suppliers) - 1)].id,
        created_by=buyer.id,
        status="received",
        ordered_at=ago(9, hour=11),
        received_at=ago(8),
        created_at=ago(9, hour=11),
    )
    lines = [(skus[0], 24), (skus[-1] if len(skus) < 5 else skus[4], 48)]
    total = Decimal("0")
    for sku, quantity in lines:
        product = products[sku]
        received.items.append(
            PurchaseItem(
                product_id=product.id,
                quantity=quantity,
                received_quantity=quantity,
                unit_cost=product.cost_price,
            )
        )
        total += product.cost_price * quantity
    received.total = total
    db.session.add(received)
    db.session.flush()
    grn = GoodsReceipt(purchase_id=received.id, received_by=stock_keeper.id, created_at=ago(8))
    db.session.add(grn)
    db.session.flush()
    for item in received.items:
        grn.items.append(
            GoodsReceiptItem(
                purchase_item_id=item.id, product_id=item.product_id, quantity=item.quantity
            )
        )
        movement = move_stock(
            products_by_id(products)[item.product_id],
            item.quantity,
            "purchase",
            stock_keeper.id,
            grn.reference,
            f"{received.reference} received",
        )
        movement.created_at = ago(8)

    on_order = Purchase(
        supplier_id=suppliers[-1].id,
        created_by=buyer.id,
        status="ordered",
        ordered_at=ago(1),
        created_at=ago(1),
        notes="Deliver before Friday",
    )
    product = products[skus[1]]
    on_order.items.append(
        PurchaseItem(product_id=product.id, quantity=40, unit_cost=product.cost_price)
    )
    on_order.total = product.cost_price * 40
    db.session.add(on_order)
    db.session.flush()


def products_by_id(products):
    return {p.id: p for p in products.values()}


def add_sales(spec, products, seller, vat_rate):
    for i, (days, method, lines) in enumerate(spec["sales"]):
        when = ago(days, hour=9 + i % 8)
        sale = Sale(
            attendant_id=seller.id,
            payment_method=method,
            total=0,
            vat_rate=vat_rate,
            created_at=when,
        )
        db.session.add(sale)
        db.session.flush()
        total = Decimal("0")
        for sku, quantity in lines:
            product = products[sku]
            sale.items.append(
                SaleItem(
                    product_id=product.id,
                    quantity=quantity,
                    unit_price=product.selling_price,
                    unit_cost=product.cost_price,
                )
            )
            total += product.selling_price * quantity
            movement = move_stock(
                product, -quantity, "sale", seller.id, sale.reference, "Point of sale"
            )
            movement.created_at = when
        sale.total = total
        sale.vat_amount = vat_included(total, vat_rate)


def add_assets(spec, users, admin, stock_keeper):
    categories = {name: AssetCategory(name=name) for name in spec["asset_categories"]}
    db.session.add_all(categories.values())
    db.session.flush()
    for name, category, serial, holder_email, condition in spec["assets"]:
        asset = Asset(
            name=name,
            category_id=categories[category].id,
            serial_number=serial,
            condition=condition,
            purchase_date=date.today() - timedelta(days=200),
        )
        db.session.add(asset)
        db.session.flush()
        audit_at(
            stock_keeper,
            "created",
            "asset",
            asset.id,
            f"{asset.asset_code} {name} registered",
            ago(30),
        )
        holder = users.get(holder_email)
        if holder:
            db.session.add(
                AssetAssignment(
                    asset_id=asset.id,
                    user_id=holder.id,
                    assigned_by=stock_keeper.id,
                    assigned_at=ago(20),
                    expected_return=date.today() + timedelta(days=60) if "laptop" in name else None,
                    condition_out=condition,
                )
            )
            asset.status = "assigned"
            asset.assigned_to = holder.id
            audit_at(
                stock_keeper,
                "assigned",
                "asset",
                asset.id,
                f"Assigned to {holder.full_name} (condition: {condition})",
                ago(20),
                {"status": ["available", "assigned"]},
            )
        if name == "Barcode scanner" and holder:
            repair = Repair(
                asset_id=asset.id,
                reported_by=holder.id,
                status="in_progress",
                urgency="high",
                description="Not reading shelf labels.",
                asset_status_before="assigned",
                started_at=ago(1),
                handled_by=stock_keeper.id,
            )
            db.session.add(repair)
            db.session.flush()
            asset.status = "in_repair"
            audit_at(holder, "repair", "asset", asset.id, f"{repair.reference} reported", ago(2))
            audit_at(
                stock_keeper,
                "repair",
                "asset",
                asset.id,
                f"{repair.reference} in progress",
                ago(1),
                {"status": ["submitted", "in_progress"]},
            )


def add_requests_and_notes(users, by_role, admin):
    employee = by_role.get("employee")
    if employee is None:
        return
    buyer = by_role.get("procurement", admin)
    paper = Request(
        requester_id=employee.id,
        item="Printer paper A4",
        quantity=5,
        urgency="normal",
        reason="Monthly reports",
        created_at=ago(2),
    )
    laptop = Request(
        requester_id=employee.id,
        item="Laptop for new hire",
        quantity=1,
        urgency="urgent",
        reason="New accounts assistant starts Monday",
        created_at=ago(1),
    )
    chairs = Request(
        requester_id=employee.id,
        item="Visitor chairs",
        quantity=4,
        urgency="low",
        reason="Reception",
        status="approved",
        reviewed_by=buyer.id,
        reviewed_at=ago(3),
        review_comment="Order with the next furniture batch",
        created_at=ago(4),
    )
    db.session.add_all([paper, laptop, chairs])
    db.session.flush()
    for req, when in ((paper, ago(2)), (laptop, ago(1)), (chairs, ago(4))):
        audit_at(
            employee, "submitted", "request", req.id, f"Submitted by {employee.full_name}", when
        )
    audit_at(
        buyer,
        "approved",
        "request",
        chairs.id,
        f"Approved by {buyer.full_name}: Order with the next furniture batch",
        ago(3),
        {"status": ["pending", "approved"]},
    )
    stock_keeper = by_role.get("inventory", admin)
    for user, message, link in [
        (admin, "Sugar 1kg is low on stock (4 left).", None),
        (stock_keeper, "Kraft Bag Medium is low on stock (8 left).", None),
        (
            buyer,
            f"Urgent request {reference('REQ', laptop.number)} from {employee.full_name}: "
            "Laptop for new hire × 1.",
            f"/approvals?open={laptop.id}",
        ),
    ]:
        db.session.add(Notification(user_id=user.id, message=message, link=link))


def seed():
    print("Seeding demo businesses…")
    for spec in (DEMO_SHOP, SECOND_SHOP):
        seed_business(spec)
    print(f"Done. Every demo user's password is {DEMO_PASSWORD}")


if __name__ == "__main__":
    with create_app().app_context():
        seed()
