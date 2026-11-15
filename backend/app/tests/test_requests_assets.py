def test_requests_crud(client, employee):
    created = client.post(
        "/api/requests/",
        json={"requester_id": employee.id, "item": "Paper", "quantity": 5, "reason": "Reports"},
    )
    assert created.status_code == 201
    assert created.json["status"] == "pending"
    assert created.json["requester_name"] == "Alex Kamau"

    bad = client.post(
        "/api/requests/",
        json={"requester_id": employee.id, "item": "Paper", "quantity": 0, "urgency": "asap"},
    )
    assert bad.status_code == 422
    assert {"quantity", "urgency", "reason"} <= set(bad.json["error"]["details"])

    assert client.get("/api/requests/?status=pending").json["count"] == 1
    assert client.delete(f"/api/requests/{created.json['id']}").status_code == 204


def test_assets_crud_and_holder_rule(client, employee):
    created = client.post("/api/assets/", json={"asset_code": "AST-0001", "name": "Laptop"})
    assert created.status_code == 201
    asset_id = created.json["id"]

    missing_holder = client.put(
        f"/api/assets/{asset_id}",
        json={"asset_code": "AST-0001", "name": "Laptop", "status": "assigned"},
    )
    assert missing_holder.status_code == 422

    assigned = client.put(
        f"/api/assets/{asset_id}",
        json={
            "asset_code": "AST-0001",
            "name": "Laptop",
            "status": "assigned",
            "assigned_to": employee.id,
        },
    )
    assert assigned.json["holder_name"] == "Alex Kamau"
    assert (
        client.post("/api/assets/", json={"asset_code": "AST-0001", "name": "X"}).status_code == 409
    )