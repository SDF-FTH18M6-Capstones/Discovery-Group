import csv
import io
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.extensions import db
from app.models import Product, Request, StockMovement


def ask(client, item, urgency="normal"):
    return client.post(
        "/api/requests/",
        json={"item": item, "quantity": 1, "urgency": urgency, "reason": "Need it"},
    ).json


def test_references_tabs_and_cancelling(as_role):
    barclay, carlos = as_role("employee"), as_role("procurement")
    pens = ask(barclay, "Pens")
    chair = ask(barclay, "Chair")
    desk = ask(barclay, "Desk")
    carlos.post(f"/api/requests/{chair['id']}/reject", json={"comment": "No budget"})

    cancelled = barclay.post(f"/api/requests/{desk['id']}/cancel")
    cancel_again = barclay.post(f"/api/requests/{desk['id']}/cancel")

    assert pens["reference"] == "REQ-0001"
    assert cancelled.json["status"] == "cancelled"
    assert cancel_again.status_code == 409
    active = barclay.get("/api/requests/?tab=active").json["results"]
    completed = barclay.get("/api/requests/?tab=completed").json["results"]
    assert [r["item"] for r in active] == ["Pens"]
    assert sorted(r["item"] for r in completed) == ["Chair", "Desk"]
    assert carlos.get("/api/requests/?status=pending").json["count"] == 1


def test_only_the_requester_can_cancel(as_role):
    barclay, other = as_role("employee"), as_role("procurement")
    pens = ask(barclay, "Pens")

    assert other.post(f"/api/requests/{pens['id']}/cancel").status_code == 403


def test_the_queue_sorts_by_urgency_then_age(as_role):
    barclay, carlos = as_role("employee"), as_role("procurement")
    for item, urgency in [
        ("A", "low"),
        ("B", "urgent"),
        ("C", "normal"),
        ("D", "urgent"),
        ("E", "high"),
    ]:
        ask(barclay, item, urgency)

    queue = carlos.get("/api/requests/?status=pending&sort=urgency").json["results"]
    urgent = carlos.get("/api/requests/?urgency=urgent").json["count"]

    assert [r["item"] for r in queue] == ["B", "D", "E", "C", "A"]
    assert urgent == 2


def test_decided_today_filter(as_role):
    barclay, carlos = as_role("employee"), as_role("procurement")
    today = ask(barclay, "Today")
    earlier = ask(barclay, "Earlier")
    carlos.post(f"/api/requests/{today['id']}/approve", json={})
    carlos.post(f"/api/requests/{earlier['id']}/approve", json={})
    row = db.session.get(Request, earlier["id"])
    row.reviewed_at = datetime.now(UTC) - timedelta(days=3)
    db.session.commit()

    decided = carlos.get("/api/requests/?decided_today=true").json["results"]

    assert [r["item"] for r in decided] == ["Today"]


def test_requests_can_point_at_a_product_and_be_fulfilled_from_the_store(as_role, category):
    product = Product(
        sku="SP-9",
        name="Toner",
        category_id=category.id,
        cost_price=Decimal("1"),
        selling_price=Decimal("2"),
    )
    db.session.add(product)
    db.session.commit()
    barclay, carlos = as_role("employee"), as_role("procurement")
    req = barclay.post(
        "/api/requests/",
        json={"item": "Toner", "product_id": product.id, "quantity": 1, "reason": "Printer"},
    ).json
    assert req["product_sku"] == "SP-9"

    too_early = carlos.post(f"/api/requests/{req['id']}/fulfil")
    carlos.post(f"/api/requests/{req['id']}/approve", json={"comment": "Take one from the store"})
    done = carlos.post(f"/api/requests/{req['id']}/fulfil")

    assert too_early.status_code == 409
    assert done.json["status"] == "fulfilled"
    timeline = barclay.get(f"/api/requests/{req['id']}/timeline").json["results"]
    assert [(e["action"], e["change"]) for e in timeline] == [
        ("Fulfilled", "Approved → Fulfilled"),
        ("Approved", "Pending → Approved"),
        ("Submitted", None),
    ]
    assert "Take one from the store" in timeline[1]["summary"]


def make_product(category, quantity=0):
    product = Product(
        sku="SP-1",
        name="Water",
        category_id=category.id,
        cost_price=Decimal("1"),
        selling_price=Decimal("2"),
        quantity=quantity,
    )
    db.session.add(product)
    db.session.commit()
    return product


def test_the_ledger_shows_quantity_after_and_references(as_role, category):
    store = as_role("inventory")
    product_id = store.post(
        "/api/products/",
        json={
            "sku": "SP-1",
            "name": "Water",
            "category_id": category.id,
            "cost_price": "1",
            "selling_price": "2",
            "quantity": 10,
        },
    ).json["id"]
    store.post(
        "/api/stock/adjustments", json={"product_id": product_id, "change": -2, "reason": "Broken"}
    )
    store.post(
        "/api/stock/adjustments", json={"product_id": product_id, "change": 5, "reason": "Recount"}
    )

    ledger = store.get(f"/api/stock/movements?product_id={product_id}").json["results"]

    assert [(m["change"], m["quantity_after"], m["reference"]) for m in ledger] == [
        (5, 13, "ADJ-0002"),
        (-2, 8, "ADJ-0001"),
        (10, 10, None),
    ]


def test_the_ledger_filters_by_date_and_exports_csv(as_role, category):
    store = as_role("inventory")
    product = make_product(category)
    old = StockMovement(
        product_id=product.id,
        change=4,
        quantity_after=4,
        type="adjustment",
        reason="=HYPERLINK(evil)",
        user_id=store.user.id,
        created_at=datetime.now(UTC) - timedelta(days=10),
    )
    db.session.add(old)
    db.session.commit()
    store.post(
        "/api/stock/adjustments", json={"product_id": product.id, "change": 1, "reason": "Found"}
    )
    today = datetime.now(UTC).date().isoformat()

    recent = store.get(f"/api/stock/movements?date_from={today}&date_to={today}").json
    exported = store.get("/api/stock/movements.csv")

    assert recent["count"] == 1
    assert exported.status_code == 200
    assert exported.mimetype == "text/csv"
    rows = list(csv.reader(io.StringIO(exported.get_data(as_text=True))))
    assert rows[0][:5] == ["Date", "Product", "SKU", "Type", "Change"]
    assert len(rows) == 3
    assert rows[2][7] == "'=HYPERLINK(evil)"
