"""Repairs, notifications, reports and the profile endpoints."""

from decimal import Decimal

from app.extensions import db
from app.models import Asset, Category, Notification, Product


def holding(user, code="AST-9", name="Laptop"):
    asset = Asset(asset_code=code, name=name, status="assigned", assigned_to=user.id)
    db.session.add(asset)
    db.session.commit()
    return asset


def messages_for(user):
    return db.session.scalars(
        db.select(Notification.message)
        .where(Notification.user_id == user.id)
        .order_by(Notification.id)
    ).all()




def test_a_repair_moves_forward_and_updates_the_asset(as_role):
    alex, store = as_role("employee"), as_role("inventory")
    laptop = holding(alex.user)

    created = alex.post("/api/repairs/", json={"asset_id": laptop.id, "description": "Keys stick"})
    assert created.status_code == 201
    repair_id = created.json["id"]
    assert created.json["reference"] == f"REP-{repair_id:03d}"
    assert created.json["status"] == "submitted"

    started = store.put(f"/api/repairs/{repair_id}/status", json={"status": "in_progress"})
    assert started.status_code == 200
    db.session.expire_all()
    assert db.session.get(Asset, laptop.id).status == "in_repair"

    done = store.put(f"/api/repairs/{repair_id}/status", json={"status": "done"})
    assert done.json["status"] == "done"
    db.session.expire_all()
    assert db.session.get(Asset, laptop.id).status == "assigned"

    back = store.put(f"/api/repairs/{repair_id}/status", json={"status": "in_progress"})
    assert back.status_code == 409
    assert back.json["error"]["message"] == "This repair is already done."

    assert messages_for(alex.user) == [
        f"Repair REP-{repair_id:03d} (Laptop) is in progress.",
        f"Repair REP-{repair_id:03d} (Laptop) is done.",
    ]
    assert messages_for(store.user) == [
        f"Repair REP-{repair_id:03d}: Laptop (AST-9) reported by {alex.user.full_name}."
    ]


def test_you_can_only_report_an_asset_you_hold(as_role, make_user):
    someone_else = make_user("employee")
    laptop = holding(someone_else)

    response = as_role("employee").post(
        "/api/repairs/", json={"asset_id": laptop.id, "description": "Not mine"}
    )

    assert response.status_code == 400
    assert response.json["error"]["message"] == "Choose an asset you hold."


def test_one_open_repair_per_asset(as_role):
    alex = as_role("employee")
    laptop = holding(alex.user)
    alex.post("/api/repairs/", json={"asset_id": laptop.id, "description": "Keys stick"})

    again = alex.post("/api/repairs/", json={"asset_id": laptop.id, "description": "Still broken"})

    assert again.status_code == 409


def test_employees_see_only_their_own_repairs(as_role):
    alex, other = as_role("employee"), as_role("employee")
    holding(alex.user, "AST-1")
    mine = alex.post(
        "/api/repairs/", json={"asset_id": holding(alex.user, "AST-2").id, "description": "Cracked"}
    ).json["id"]
    theirs = other.post(
        "/api/repairs/",
        json={"asset_id": holding(other.user, "AST-3").id, "description": "Dead battery"},
    ).json["id"]

    assert [r["id"] for r in alex.get("/api/repairs/").json["results"]] == [mine]
    assert alex.get(f"/api/repairs/{theirs}").status_code == 404
    assert as_role("inventory").get("/api/repairs/").json["count"] == 2


def test_short_description_is_422(as_role):
    alex = as_role("employee")
    response = alex.post(
        "/api/repairs/", json={"asset_id": holding(alex.user).id, "description": " "}
    )

    assert response.status_code == 422
    assert "description" in response.json["error"]["details"]




def test_requests_notify_procurement_then_the_requester(as_role):
    alex, jane = as_role("employee"), as_role("procurement")

    request_id = alex.post(
        "/api/requests/",
        json={"item": "Laptop", "quantity": 1, "urgency": "urgent", "reason": "New hire"},
    ).json["id"]
    jane.post(f"/api/requests/{request_id}/reject", json={"comment": "Use the spare one"})

    assert messages_for(jane.user) == [f"Urgent request from {alex.user.full_name}: Laptop × 1."]
    assert messages_for(alex.user) == ["Your request for Laptop was rejected: Use the spare one"]


def test_a_role_change_is_announced_to_that_person(admin, employee):
    employee_id = employee.id
    admin.put(f"/api/users/{employee_id}/role", json={"role": "sales"})

    messages = db.session.scalars(
        db.select(Notification.message).where(Notification.user_id == employee_id)
    ).all()
    assert messages == ["Your role is now Sales Attendant."]


def test_people_read_only_their_own_notifications(as_role, make_user):
    me, someone = as_role("employee"), make_user("employee")
    db.session.add_all(
        [
            Notification(user_id=me.user.id, message="One"),
            Notification(user_id=me.user.id, message="Two"),
            Notification(user_id=someone.id, message="Private"),
        ]
    )
    db.session.commit()
    private = db.session.scalar(db.select(Notification.id).where(Notification.message == "Private"))

    listed = me.get("/api/notifications/").json
    assert [n["message"] for n in listed["results"]] == ["Two", "One"]
    assert me.post(f"/api/notifications/{private}/read").status_code == 404

    first = listed["results"][0]["id"]
    assert me.post(f"/api/notifications/{first}/read").json["is_read"] is True
    assert me.get("/api/notifications/?unread=true").json["count"] == 1
    assert me.post("/api/notifications/read-all").json == {"updated": 1}
    assert me.get("/api/notifications/?unread=true").json["count"] == 0




def test_the_summary_adds_up_sales_and_stock(as_role):
    category = Category(name="Beverages")
    db.session.add(category)
    db.session.flush()
    water = Product(
        sku="SP-1",
        name="Water",
        category_id=category.id,
        cost_price=Decimal("180"),
        selling_price=Decimal("250"),
        quantity=10,
        reorder_level=9,
    )
    db.session.add(water)
    db.session.commit()
    seller = as_role("sales")
    seller.post(
        "/api/sales/",
        json={"payment_method": "cash", "items": [{"product_id": water.id, "quantity": 2}]},
    )
    seller.post(
        "/api/sales/",
        json={"payment_method": "card", "items": [{"product_id": water.id, "quantity": 1}]},
    )

    report = as_role("admin").get("/api/reports/summary?days=7")

    assert report.status_code == 200
    body = report.json
    assert body["sales_total"] == "750.00"
    assert body["sales_count"] == 2
    assert body["average_sale"] == "375.00"
    assert body["estimated_profit"] == "210.00"  # 3 × (250 − 180)
    assert body["stock_value"] == "1260.00"  # 7 left × 180
    assert len(body["by_day"]) == 7
    assert body["by_day"][-1]["total"] == "750.00"
    assert body["top_products"] == [
        {"product_id": water.id, "name": "Water", "quantity": 3, "total": "750.00"}
    ]
    assert [p["name"] for p in body["low_stock"]] == ["Water"]


def test_report_days_are_checked(admin):
    assert admin.get("/api/reports/summary?days=0").status_code == 422
    assert admin.get("/api/reports/summary?days=400").status_code == 422




def test_you_can_change_your_own_name(as_role):
    me = as_role("employee")

    response = me.put("/api/auth/me", json={"full_name": "  Alex K.  "})

    assert response.json["full_name"] == "Alex K."
    assert me.get("/api/auth/me").json["full_name"] == "Alex K."


def test_changing_password_needs_the_current_one(as_role, client):
    me = as_role("employee")

    wrong = me.post(
        "/api/auth/password", json={"current_password": "Nope1234", "new_password": "Better1234"}
    )
    weak = me.post(
        "/api/auth/password", json={"current_password": "Secret123!", "new_password": "short"}
    )
    ok = me.post(
        "/api/auth/password", json={"current_password": "Secret123!", "new_password": "Better1234"}
    )

    assert wrong.status_code == 422
    assert wrong.json["error"]["details"] == {
        "current_password": ["Your current password is not correct."]
    }
    assert weak.status_code == 422
    assert "new_password" in weak.json["error"]["details"]
    assert ok.json == {"message": "Password changed."}
    email = me.user.email
    login = client.post("/api/auth/login", json={"email": email, "password": "Better1234"})
    assert login.status_code == 200