def test_categories_crud(client):
    created = client.post("/api/categories/", json={"name": "Grocery"})
    assert created.status_code == 201
    category_id = created.json["id"]

    assert client.post("/api/categories/", json={"name": "Grocery"}).status_code == 409
    renamed = client.put(f"/api/categories/{category_id}", json={"name": "Food"})
    assert renamed.json["name"] == "Food"
    assert client.delete(f"/api/categories/{category_id}").status_code == 204


def test_suppliers_crud_and_validation(client):
    bad = client.post("/api/suppliers/", json={"name": "Metro", "email": "not-an-email"})
    assert bad.status_code == 422

    created = client.post(
        "/api/suppliers/",
        json={"name": "Metro", "email": "a@metro.co.ke", "phone": "+254700000001"},
    )
    assert created.status_code == 201
    supplier_id = created.json["id"]

    updated = client.put(f"/api/suppliers/{supplier_id}", json={"name": "Metro Wholesale"})
    assert updated.json["name"] == "Metro Wholesale"
    assert client.get("/api/suppliers/?search=wholesale").json["count"] == 1
    assert client.delete(f"/api/suppliers/{supplier_id}").status_code == 204