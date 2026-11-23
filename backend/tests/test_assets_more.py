from datetime import date, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Asset, AssetAssignment


def test_register_with_category_serial_and_purchase_details(as_role):
    store = as_role("inventory")
    laptops = store.post("/api/asset-categories/", json={"name": "Laptops"}).json

    asset = store.post(
        "/api/assets/",
        json={
            "name": "Dell Latitude",
            "category_id": laptops["id"],
            "serial_number": "SN-123",
            "purchase_date": "2026-01-15",
            "purchase_cost": "95000.00",
            "condition": "new",
        },
    ).json

    assert asset["asset_code"] == "AST-0001"
    assert asset["barcode"].startswith("SP")
    assert asset["category_name"] == "Laptops"
    assert store.get(f"/api/assets/lookup/{asset['barcode']}").json["id"] == asset["id"]
    assert store.get("/api/assets/lookup/ast-0001").json["id"] == asset["id"]
    assert store.get("/api/assets/?search=SN-123").json["count"] == 1
    assert store.delete(f"/api/asset-categories/{laptops['id']}").status_code == 409


def test_assign_and_return_keep_the_full_history(as_role, outbox):
    store, keith = as_role("inventory"), as_role("employee")
    asset_id = store.post("/api/assets/", json={"name": "Laptop"}).json["id"]
    due = (date.today() + timedelta(days=30)).isoformat()

    assigned = store.post(
        f"/api/assets/{asset_id}/assign",
        json={"user_id": keith.user.id, "condition": "good", "expected_return": due},
    ).json
    twice = store.post(
        f"/api/assets/{asset_id}/assign", json={"user_id": keith.user.id, "condition": "good"}
    )
    mine = keith.get("/api/assets/").json["results"]
    returned = store.post(
        f"/api/assets/{asset_id}/return", json={"condition": "fair", "notes": "Scratched lid"}
    ).json
    again = store.post(f"/api/assets/{asset_id}/return", json={"condition": "fair"})

    assert assigned["status"] == "assigned"
    assert assigned["current_assignment"]["expected_return"] == due
    assert twice.status_code == 409
    assert [a["id"] for a in mine] == [asset_id]
    assert outbox[-1]["subject"] == "Laptop assigned to you"
    assert returned["status"] == "available"
    assert returned["condition"] == "fair"
    assert returned["current_assignment"] is None
    assert again.status_code == 409
    history = store.get(f"/api/assets/{asset_id}/assignments").json["results"]
    assert len(history) == 1
    assert (history[0]["condition_out"], history[0]["condition_in"]) == ("good", "fair")
    assert history[0]["received_by_name"] == store.user.full_name
    timeline = [e["action"] for e in store.get(f"/api/assets/{asset_id}/timeline").json["results"]]
    assert timeline == ["Returned", "Assigned", "Created"]


def test_the_database_allows_one_open_assignment_per_asset(as_role):
    store, keith = as_role("inventory"), as_role("employee")
    asset = Asset(name="Phone")
    db.session.add(asset)
    db.session.flush()
    for _ in range(2):
        db.session.add(
            AssetAssignment(
                asset_id=asset.id,
                user_id=keith.user.id,
                assigned_by=store.user.id,
                condition_out="good",
            )
        )
    with pytest.raises(IntegrityError):
        db.session.flush()
    db.session.rollback()


def test_overdue_assignments(as_role):
    store, keith = as_role("inventory"), as_role("employee")
    late = store.post("/api/assets/", json={"name": "Projector"}).json["id"]
    on_time = store.post("/api/assets/", json={"name": "Camera"}).json["id"]
    for asset_id in (late, on_time):
        store.post(
            f"/api/assets/{asset_id}/assign", json={"user_id": keith.user.id, "condition": "good"}
        )
    row = db.session.scalar(db.select(AssetAssignment).filter_by(asset_id=late))
    row.expected_return = date.today() - timedelta(days=2)
    db.session.commit()

    overdue = store.get("/api/assets/?overdue=true").json["results"]
    past = store.post(
        f"/api/assets/{late}/assign",
        json={"user_id": keith.user.id, "condition": "good", "expected_return": "2020-01-01"},
    )

    assert [a["id"] for a in overdue] == [late]
    assert overdue[0]["current_assignment"]["is_overdue"] is True
    assert past.status_code == 409 


def test_retire_only_available_assets(as_role):
    store, keith = as_role("inventory"), as_role("employee")
    asset_id = store.post(
        "/api/assets/", json={"name": "Chair", "assigned_to": keith.user.id}
    ).json["id"]

    held = store.post(f"/api/assets/{asset_id}/retire")
    store.post(f"/api/assets/{asset_id}/return", json={"condition": "poor"})
    retired = store.post(f"/api/assets/{asset_id}/retire")

    assert held.status_code == 409
    assert retired.json["status"] == "retired"
    assert (
        store.post(
            f"/api/assets/{asset_id}/assign", json={"user_id": keith.user.id, "condition": "poor"}
        ).status_code
        == 409
    )


def test_a_repair_can_be_rejected_with_a_reason(as_role):
    store, keith = as_role("inventory"), as_role("employee")
    asset_id = store.post(
        "/api/assets/", json={"name": "Laptop", "assigned_to": keith.user.id}
    ).json["id"]
    repair = keith.post(
        "/api/repairs/",
        json={"asset_id": asset_id, "description": "Sticker peeling", "urgency": "low"},
    ).json

    rejected = store.put(
        f"/api/repairs/{repair['id']}/status",
        json={"status": "rejected", "resolution": "Cosmetic only"},
    ).json
    after = store.put(f"/api/repairs/{repair['id']}/status", json={"status": "in_progress"})

    assert rejected["status"] == "rejected"
    assert rejected["resolution"] == "Cosmetic only"
    assert after.status_code == 409
    assert store.get(f"/api/assets/{asset_id}").json["status"] == "assigned"
    assert (
        keith.post(
            "/api/repairs/", json={"asset_id": asset_id, "description": "Battery dead"}
        ).status_code
        == 201
    )


def test_in_progress_repairs_cannot_be_rejected_and_block_returns(as_role):
    store, keith = as_role("inventory"), as_role("employee")
    asset_id = store.post(
        "/api/assets/", json={"name": "Laptop", "assigned_to": keith.user.id}
    ).json["id"]
    repair_id = keith.post(
        "/api/repairs/", json={"asset_id": asset_id, "description": "Won't boot"}
    ).json["id"]
    store.put(f"/api/repairs/{repair_id}/status", json={"status": "in_progress"})

    reject = store.put(
        f"/api/repairs/{repair_id}/status", json={"status": "rejected", "resolution": "x"}
    )
    give_back = store.post(f"/api/assets/{asset_id}/return", json={"condition": "poor"})
    open_list = store.get("/api/repairs/?status=open").json

    assert reject.status_code == 409
    assert give_back.status_code == 409
    assert open_list["count"] == 1
    assert store.get(f"/api/assets/{asset_id}").json["open_repair"]["status"] == "in_progress"
