import io
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from PIL import Image as PILImage

from app.extensions import db
from app.models import Category, Image, Product, Sale, SaleItem


@pytest.fixture()
def water(app, category):
    product = Product(
        sku="SP-1",
        name="Water",
        category_id=category.id,
        cost_price=Decimal("180"),
        selling_price=Decimal("250"),
        quantity=3,
        reorder_level=5,
    )
    db.session.add(product)
    db.session.commit()
    return product


def tiles(client):
    return {t["key"]: t for t in client.get("/api/dashboard/pulse").json["tiles"]}


def test_pulse_follows_the_role_and_matches_the_lists(as_role, water):
    employee, buyer = as_role("employee"), as_role("procurement")
    employee.post(
        "/api/requests/", json={"item": "Desk", "quantity": 1, "urgency": "urgent", "reason": "New"}
    )
    employee.post("/api/requests/", json={"item": "Pens", "quantity": 1, "reason": "Out"})
    admin, store, seller = as_role("admin"), as_role("inventory"), as_role("sales")
    seller.post(
        "/api/sales/",
        json={"payment_method": "cash", "items": [{"product_id": water.id, "quantity": 1}]},
    )

    admin_tiles = tiles(admin)
    assert list(admin_tiles) == [
        "low_stock",
        "approvals",
        "awaiting_receipt",
        "open_repairs",
        "sales_today",
    ]
    assert (
        admin_tiles["low_stock"]["count"]
        == admin.get("/api/products/?low_stock=true").json["count"]
        == 1
    )
    assert admin_tiles["approvals"]["count"] == 2
    assert admin_tiles["approvals"]["detail"] == "1 urgent"
    assert admin_tiles["approvals"]["tone"] == "danger"
    assert admin_tiles["sales_today"]["amount"] == "250.00"
    assert list(tiles(buyer)) == ["approvals", "awaiting_receipt", "my_requests"]
    assert list(tiles(store)) == ["low_stock", "awaiting_receipt", "open_repairs", "overdue_assets"]
    assert tiles(seller)["my_sales_today"]["count"] == 1
    assert tiles(employee)["my_requests"]["count"] == 2


def test_product_timeline_merges_edits_and_stock_moves(as_role, category):
    store = as_role("inventory")
    product = store.post(
        "/api/products/",
        json={
            "sku": "SP-2",
            "name": "Tea",
            "category_id": category.id,
            "cost_price": "10.00",
            "selling_price": "15.00",
            "quantity": 30,
        },
    ).json
    store.put(
        f"/api/products/{product['id']}",
        json={
            "sku": "SP-2",
            "name": "Tea",
            "category_id": category.id,
            "cost_price": "10.00",
            "selling_price": "18.00",
        },
    )
    store.post(
        "/api/stock/adjustments", json={"product_id": product["id"], "change": -2, "reason": "Torn"}
    )

    entries = store.get(f"/api/products/{product['id']}/timeline").json["results"]

    assert [(e["action"], e["change"]) for e in entries] == [
        ("Adjusted", "-2 (now 28)"),
        ("Updated", "Selling price 15.00 → 18.00"),
        ("Adjusted", "+30 (now 30)"),
        ("Created", None),
    ]
    assert entries[0]["reference"] == "ADJ-0001"
    assert entries[0]["user_name"] == store.user.full_name


def test_reports_take_a_custom_range_and_subtract_expenses(as_role, water, make_user):
    admin = as_role("admin")
    seller = make_user("sales")
    in_range = datetime.now(UTC) - timedelta(days=20)
    for when, quantity in [(in_range, 2), (datetime.now(UTC) - timedelta(days=60), 5)]:
        sale = Sale(
            attendant_id=seller.id,
            payment_method="mpesa",
            total=Decimal("250") * quantity,
            created_at=when,
        )
        sale.items.append(
            SaleItem(
                product_id=water.id,
                quantity=quantity,
                unit_price=Decimal("250"),
                unit_cost=Decimal("180"),
            )
        )
        db.session.add(sale)
    db.session.commit()
    start = (date.today() - timedelta(days=30)).isoformat()
    end = date.today().isoformat()
    admin.post("/api/expenses/", json={"spent_on": end, "category": "Rent", "amount": "100.00"})
    admin.post(
        "/api/expenses/", json={"spent_on": "2020-01-01", "category": "Rent", "amount": "999.00"}
    )

    report = admin.get(f"/api/reports/summary?date_from={start}&date_to={end}").json

    assert report["days"] == 31
    assert report["sales_total"] == "500.00"
    assert report["gross_profit"] == "140.00"
    assert report["expenses_total"] == "100.00"
    assert report["net_profit"] == "40.00"
    assert report["by_payment"] == [
        {"key": "mpesa", "label": "M-Pesa", "total": "500.00", "count": 1}
    ]
    assert report["expenses_by_category"][0]["label"] == "Rent"


def test_report_ranges_are_checked(as_role):
    admin = as_role("admin")

    half = admin.get("/api/reports/summary?date_from=2026-01-01")
    backwards = admin.get("/api/reports/summary?date_from=2026-02-01&date_to=2026-01-01")
    too_long = admin.get("/api/reports/summary?date_from=2024-01-01&date_to=2026-01-01")

    assert half.status_code == backwards.status_code == too_long.status_code == 422


def picture(fmt="PNG", size=(2400, 1200)):
    out = io.BytesIO()
    PILImage.new("RGB", size, (200, 30, 30)).save(out, format=fmt)
    out.seek(0)
    return out


def test_photos_are_resized_served_and_replaced(as_role, water, client):
    store = as_role("inventory")

    first = store.post(
        f"/api/products/{water.id}/photo",
        data={"photo": (picture(), "water.png")},
        content_type="multipart/form-data",
    )
    assert first.status_code == 200
    url = first.json["image_url"]
    served = client.get(url)
    assert served.mimetype == "image/webp"
    assert PILImage.open(io.BytesIO(served.data)).size == (1200, 600)

    second = store.post(
        f"/api/products/{water.id}/photo",
        data={"photo": (picture("JPEG", (300, 300)), "water.jpg")},
        content_type="multipart/form-data",
    )
    assert second.json["image_url"] != url
    assert client.get(url).status_code == 404
    assert db.session.scalar(db.select(db.func.count(Image.id))) == 1


def test_only_real_images_under_five_megabytes(as_role, water):
    store = as_role("inventory")

    fake = store.post(
        f"/api/products/{water.id}/photo",
        data={"photo": (io.BytesIO(b"%PDF-1.4 not an image"), "doc.pdf")},
        content_type="multipart/form-data",
    )
    gif = io.BytesIO()
    PILImage.new("RGB", (10, 10)).save(gif, format="GIF")
    gif.seek(0)
    wrong_type = store.post(
        f"/api/products/{water.id}/photo",
        data={"photo": (gif, "a.gif")},
        content_type="multipart/form-data",
    )
    huge = store.post(
        f"/api/products/{water.id}/photo",
        data={"photo": (io.BytesIO(b"x" * (5 * 1024 * 1024 + 10)), "big.png")},
        content_type="multipart/form-data",
    )

    assert fake.status_code == 400
    assert wrong_type.status_code == 400
    assert huge.status_code == 413


def test_categories_can_be_deactivated(as_role):
    store = as_role("inventory")
    created = store.post("/api/categories/", json={"name": "Seasonal"}).json

    store.put(f"/api/categories/{created['id']}", json={"name": "Seasonal", "is_active": False})

    assert store.get("/api/categories/?active=true").json["count"] == 0
    assert db.session.get(Category, created["id"]).is_active is False
