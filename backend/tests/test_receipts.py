import io
import json
from datetime import date
from decimal import Decimal

from app.extensions import db
from app.models import Product, Purchase, StockMovement, Supplier
from app.receipts import clean_reading, parse_receipt_text

SUPERMARKET = """NAIVAS SUPERMARKET LTD
Moi Avenue, Nairobi
PIN: P051234567X
TAX INVOICE
Date: 21/11/2026 14:32
Receipt No: 0045-778812
SUGAR 1KG
2.000 X 165.00      330.00
COOKING OIL 2L      520.00
BREAD 400G
3 x 65.00           195.00
SUBTOTAL          1,045.00
VAT 16%             144.14
TOTAL             1,045.00
CASH              1,100.00
CHANGE               55.00
"""

WHOLESALER = """Metro Wholesale
Tel 0711000111
Invoice #INV-2291
12 Nov 2026
Exercise books 10 @ 45.00 450.00
Biro pens 20 x 10.00 200.00
Total Ksh 650.00
Paid M-PESA 650.00"""


def product(name, sku, cost="100.00", quantity=0, category=None):
    item = Product(
        name=name,
        sku=sku,
        category_id=category.id,
        cost_price=Decimal(cost),
        selling_price=Decimal(cost) * 2,
        quantity=quantity,
    )
    db.session.add(item)
    db.session.commit()
    return item


def test_a_supermarket_receipt_is_read():
    reading = parse_receipt_text(SUPERMARKET)

    assert reading["supplier"] == "NAIVAS SUPERMARKET LTD"
    assert reading["date"] == date(2026, 11, 21)
    assert reading["number"] == "0045-778812"
    assert (reading["total"], reading["tax"]) == (Decimal("1045.00"), Decimal("144.14"))
    assert [(i["description"], i["quantity"], i["unit_price"]) for i in reading["items"]] == [
        ("SUGAR 1KG", 2, Decimal("165.00")),
        ("COOKING OIL 2L", 1, Decimal("520.00")),
        ("BREAD 400G", 3, Decimal("65.00")),
    ]


def test_a_wholesaler_invoice_is_read():
    reading = parse_receipt_text(WHOLESALER)

    assert (reading["supplier"], reading["number"]) == ("Metro Wholesale", "INV-2291")
    assert reading["date"] == date(2026, 11, 12)
    assert reading["total"] == Decimal("650.00")
    assert [(i["description"], i["quantity"]) for i in reading["items"]] == [
        ("Exercise books", 10),
        ("Biro pens", 20),
    ]


def test_without_a_total_line_the_items_are_added_up():
    reading = parse_receipt_text("Mama Pima Shop\nTomatoes 120.00\nOnions 80.00")

    assert reading["total"] == Decimal("200.00")
    assert reading["tax"] is None


def test_odd_ai_answers_are_cleaned():
    reading = clean_reading(
        {
            "supplier": "Quickmart",
            "date": "not a date",
            "total": "1,250.5",
            "items": [
                {"description": "Rice 2kg", "quantity": 2, "amount": 500},
                {"description": "", "amount": 10},
                {"description": "Soap", "amount": None},
            ],
        }
    )

    assert (reading["date"], reading["total"], reading["tax"]) == (None, Decimal("1250.50"), None)
    assert reading["items"] == [
        {
            "description": "Rice 2kg",
            "quantity": 2,
            "unit_price": Decimal("250.00"),
            "amount": Decimal("500.00"),
        }
    ]


def test_text_from_the_phone_is_matched_to_products_and_suppliers(admin, category):
    sugar = product("Sugar 1kg", "SUG-1", category=category)
    oil = product("Cooking Oil 2L", "OIL-2", category=category)
    db.session.add(Supplier(name="Naivas Supermarket"))
    db.session.commit()

    reading = admin.post("/api/receipts/text", json={"text": SUPERMARKET}).json

    assert reading["supplier_id"] is not None
    assert [i["product_id"] for i in reading["items"]] == [sugar.id, oil.id, None]
    assert reading["total"] == "1045.00"
    assert reading["date"] == "2026-11-21"


def test_blank_text_is_refused(admin):
    response = admin.post("/api/receipts/text", json={"text": "  "})

    assert response.status_code == 422


def test_the_reader_reports_its_mode_and_what_the_user_can_do(app, as_role):
    as_role("procurement")
    as_role("inventory")
    admin = as_role("admin")

    assert admin.get("/api/receipts/reader").json == {
        "mode": "device",
        "can_expense": True,
        "can_stock": False,
    }
    app.config["RECEIPT_AI_KEY"] = "key"
    assert as_role("procurement").get("/api/receipts/reader").json == {
        "mode": "ai",
        "can_expense": False,
        "can_stock": True,
    }


def test_photos_need_the_online_reader(admin):
    response = admin.post(
        "/api/receipts/photo",
        data={"photo": (io.BytesIO(b"x"), "r.jpg", "image/jpeg")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 409


class FakeReply:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def test_a_photo_is_read_online_when_a_key_is_set(app, admin, monkeypatch):
    app.config["RECEIPT_AI_KEY"] = "secret"
    sent = {}

    def fake_open(request, timeout):
        sent["headers"] = dict(request.header_items())
        sent["body"] = json.loads(request.data)
        answer = {
            "supplier": "Quickmart",
            "date": "2026-11-20",
            "number": "Q-881",
            "total": 300,
            "tax": None,
            "items": [
                {"description": "Milk 500ml", "quantity": 5, "unit_price": 60, "amount": 300}
            ],
        }
        return FakeReply(
            {"content": [{"type": "text", "text": "```json\n" + json.dumps(answer) + "\n```"}]}
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    response = admin.post(
        "/api/receipts/photo",
        data={"photo": (io.BytesIO(b"\xff\xd8photo"), "r.jpg", "image/jpeg")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert (response.json["supplier"], response.json["total"]) == ("Quickmart", "300.00")
    assert response.json["items"][0]["quantity"] == "5"
    assert sent["headers"]["X-api-key"] == "secret"
    assert sent["body"]["messages"][0]["content"][0]["source"]["media_type"] == "image/jpeg"


def test_online_reading_failures_are_explained(app, admin, monkeypatch):
    app.config["RECEIPT_AI_KEY"] = "secret"

    def broken(request, timeout):
        raise TimeoutError

    monkeypatch.setattr("urllib.request.urlopen", broken)
    photo = {"photo": (io.BytesIO(b"x"), "r.jpg", "image/jpeg")}
    response = admin.post("/api/receipts/photo", data=photo, content_type="multipart/form-data")

    assert response.status_code == 502
    assert "online" in response.json["error"]["message"]


def test_photo_checks(app, admin):
    app.config["RECEIPT_AI_KEY"] = "secret"

    missing = admin.post("/api/receipts/photo", data={}, content_type="multipart/form-data")
    wrong = admin.post(
        "/api/receipts/photo",
        data={"photo": (io.BytesIO(b"x"), "r.gif", "image/gif")},
        content_type="multipart/form-data",
    )

    assert (missing.status_code, wrong.status_code) == (400, 422)


def test_a_receipt_becomes_a_received_purchase(as_role, category):
    buyer = as_role("procurement")
    sugar = product("Sugar 1kg", "SUG-1", cost="150.00", quantity=10, category=category)
    oil = product("Cooking Oil 2L", "OIL-2", cost="500.00", category=category)

    response = buyer.post(
        "/api/receipts/stock",
        json={
            "supplier_name": "Naivas Supermarket",
            "number": "0045-778812",
            "lines": [
                {"product_id": sugar.id, "quantity": 10, "unit_cost": "170.00"},
                {"product_id": oil.id, "quantity": 2, "unit_cost": "520.00"},
            ],
        },
    )

    assert response.status_code == 201
    assert response.json["total"] == "2740.00"
    purchase = db.session.get(Purchase, response.json["purchase_id"])
    assert (purchase.source, purchase.status) == ("receipt", "received")
    assert purchase.supplier.name == "Naivas Supermarket"
    assert "0045-778812" in purchase.notes
    db.session.refresh(sugar)
    assert (sugar.quantity, sugar.cost_price) == (20, Decimal("160.00"))
    moves = db.session.scalars(db.select(StockMovement).where(StockMovement.type == "purchase"))
    assert sorted(m.change for m in moves) == [2, 10]


def test_an_existing_supplier_is_reused_and_repeated_lines_are_combined(as_role, category):
    buyer = as_role("inventory")
    metro = Supplier(name="Metro Wholesale")
    db.session.add(metro)
    db.session.commit()
    books = product("Exercise books", "BK-1", cost="40.00", category=category)

    response = buyer.post(
        "/api/receipts/stock",
        json={
            "supplier_name": "metro wholesale",
            "lines": [
                {"product_id": books.id, "quantity": 4, "unit_cost": "45.00"},
                {"product_id": books.id, "quantity": 6, "unit_cost": "40.00"},
            ],
        },
    )

    purchase = db.session.get(Purchase, response.json["purchase_id"])
    assert purchase.supplier_id == metro.id
    assert [(i.quantity, i.unit_cost) for i in purchase.items] == [(10, Decimal("42.00"))]
    assert db.session.scalar(db.select(db.func.count(Supplier.id))) == 1


def test_stock_purchase_checks(as_role, category):
    buyer = as_role("procurement")
    old = product("Old stock", "OLD-1", category=category)
    old.is_active = False
    db.session.commit()
    line = [{"product_id": old.id, "quantity": 1, "unit_cost": "1.00"}]

    nobody = buyer.post("/api/receipts/stock", json={"lines": line})
    ghost = buyer.post(
        "/api/receipts/stock",
        json={"supplier_id": 999, "lines": line},
    )
    unknown = buyer.post(
        "/api/receipts/stock",
        json={"supplier_name": "Shop", "lines": [{**line[0], "product_id": 999}]},
    )
    retired = buyer.post("/api/receipts/stock", json={"supplier_name": "Shop", "lines": line})

    assert nobody.status_code == 422
    assert ghost.status_code == 400
    assert unknown.status_code == 400
    assert retired.status_code == 409


def test_only_buyers_and_storekeepers_add_stock_from_receipts(as_role, category):
    as_role("procurement")
    as_role("inventory")
    sugar = product("Sugar 1kg", "SUG-1", category=category)
    body = {
        "supplier_name": "Shop",
        "lines": [{"product_id": sugar.id, "quantity": 1, "unit_cost": "1.00"}],
    }

    assert as_role("admin").post("/api/receipts/stock", json=body).status_code == 403
    assert as_role("sales").post("/api/receipts/stock", json=body).status_code == 403
    assert as_role("sales").get("/api/receipts/reader").status_code == 403
