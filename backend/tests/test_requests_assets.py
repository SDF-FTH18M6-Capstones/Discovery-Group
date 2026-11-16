import pytest

REQUEST = {"item": "Printer paper", "quantity": 5, "urgency": "high", "reason": "Monthly reports"}


@pytest.fixture()
def employee_client(as_role):
    return as_role("employee")


@pytest.fixture()
def manager(as_role):
    return as_role("procurement")


def make_request(client):
    response = client.post("/api/requests/", json=REQUEST)
    assert response.status_code == 201
    return response.json


def test_a_request_belongs_to_whoever_made_it(employee_client):
    created = make_request(employee_client)

    assert created["requester_id"] == employee_client.user.id
    assert created["requester_name"] == employee_client.user.full_name
    assert created["status"] == "pending"


def test_employees_see_only_their_own_requests(as_role, employee_client):
    other = as_role("employee")
    mine = make_request(employee_client)
    theirs = make_request(other)

    listed = employee_client.get("/api/requests/").json
    assert [r["id"] for r in listed["results"]] == [mine["id"]]
    assert employee_client.get(f"/api/requests/{theirs['id']}").status_code == 404


def test_procurement_and_admin_see_every_request(as_role, employee_client, manager):
    make_request(employee_client)
    make_request(as_role("sales"))

    assert manager.get("/api/requests/").json["count"] == 2
    assert as_role("admin").get("/api/requests/").json["count"] == 2


def test_owner_can_edit_and_delete_while_pending(employee_client):
    created = make_request(employee_client)
    url = f"/api/requests/{created['id']}"

    edited = employee_client.put(url, json={**REQUEST, "quantity": 10})
    assert edited.status_code == 200
    assert edited.json["quantity"] == 10
    assert employee_client.delete(url).status_code == 204


def test_a_manager_cannot_edit_someone_elses_request(employee_client, manager):
    created = make_request(employee_client)

    response = manager.put(f"/api/requests/{created['id']}", json=REQUEST)

    assert response.status_code == 403


def test_procurement_manager_approves_with_a_comment(employee_client, manager):
    created = make_request(employee_client)

    response = manager.post(
        f"/api/requests/{created['id']}/approve", json={"comment": "Order from Metro"}
    )

    assert response.status_code == 200
    assert response.json["status"] == "approved"
    assert response.json["reviewed_by"] == manager.user.id
    assert response.json["review_comment"] == "Order from Metro"
    assert response.json["reviewed_at"]


def test_rejecting_needs_a_reason(employee_client, manager):
    created = make_request(employee_client)
    url = f"/api/requests/{created['id']}/reject"

    assert manager.post(url, json={}).status_code == 422
    assert manager.post(url, json={"comment": ""}).status_code == 422
    rejected = manager.post(url, json={"comment": "No budget this month"})
    assert rejected.status_code == 200
    assert rejected.json["status"] == "rejected"


def test_a_request_is_decided_only_once(employee_client, manager):
    created = make_request(employee_client)
    manager.post(f"/api/requests/{created['id']}/approve", json={})

    again = manager.post(f"/api/requests/{created['id']}/reject", json={"comment": "Changed mind"})

    assert again.status_code == 409


def test_a_procurement_manager_cannot_approve_their_own_request(manager):
    created = make_request(manager)

    response = manager.post(f"/api/requests/{created['id']}/approve", json={})

    assert response.status_code == 403
    assert response.json["error"]["message"] == "You cannot approve or reject your own request."


def test_the_admin_cannot_approve(employee_client, as_role):
    created = make_request(employee_client)

    response = as_role("admin").post(f"/api/requests/{created['id']}/approve", json={})

    assert response.status_code == 403


def test_owner_cannot_edit_after_the_decision(employee_client, manager):
    created = make_request(employee_client)
    manager.post(f"/api/requests/{created['id']}/approve", json={})

    assert employee_client.put(f"/api/requests/{created['id']}", json=REQUEST).status_code == 409
    assert employee_client.delete(f"/api/requests/{created['id']}").status_code == 409


def test_filter_requests_by_status(employee_client, manager):
    first = make_request(employee_client)
    make_request(employee_client)
    manager.post(f"/api/requests/{first['id']}/approve", json={})

    assert manager.get("/api/requests/?status=pending").json["count"] == 1
    assert manager.get("/api/requests/?status=approved").json["count"] == 1


# ---------- assets ----------


def test_assets_crud_and_holder_rule(admin, employee):
    created = admin.post("/api/assets/", json={"asset_code": "AST-0001", "name": "Laptop"})
    assert created.status_code == 201
    asset_id = created.json["id"]

    missing_holder = admin.put(
        f"/api/assets/{asset_id}",
        json={"asset_code": "AST-0001", "name": "Laptop", "status": "assigned"},
    )
    assert missing_holder.status_code == 422

    assigned = admin.put(
        f"/api/assets/{asset_id}",
        json={
            "asset_code": "AST-0001",
            "name": "Laptop",
            "status": "assigned",
            "assigned_to": employee.id,
        },
    )
    assert assigned.json["holder_name"] == employee.full_name


def test_employees_see_only_the_assets_they_hold(admin, as_role):
    holder = as_role("employee")
    stranger = as_role("employee")
    admin.post("/api/assets/", json={"asset_code": "AST-1", "name": "Spare chair"})
    mine = admin.post(
        "/api/assets/",
        json={
            "asset_code": "AST-2",
            "name": "Laptop",
            "status": "assigned",
            "assigned_to": holder.user.id,
        },
    ).json

    assert [a["id"] for a in holder.get("/api/assets/").json["results"]] == [mine["id"]]
    assert stranger.get("/api/assets/").json["count"] == 0
    assert stranger.get(f"/api/assets/{mine['id']}").status_code == 404
    assert admin.get("/api/assets/").json["count"] == 2