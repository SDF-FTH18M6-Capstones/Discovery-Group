def test_categories_crud(admin):
    created = admin.post("/api/categories/", json={"name": "Grocery"})
    assert created.status_code == 201
    category_id = created.json["id"]

    assert admin.post("/api/categories/", json={"name": "Grocery"}).status_code == 409
    renamed = admin.put(f"/api/categories/{category_id}", json={"name": "Food"})
    assert renamed.json["name"] == "Food"
    assert admin.delete(f"/api/categories/{category_id}").status_code == 204


def test_suppliers_crud_and_validation(admin):
    bad = admin.post("/api/suppliers/", json={"name": "Metro", "email": "not-an-email"})
    assert bad.status_code == 422

    created = admin.post(
        "/api/suppliers/",
        json={"name": "Metro", "email": "a@metro.co.ke", "phone": "+254700000001"},
    )
    assert created.status_code == 201
    supplier_id = created.json["id"]

    updated = admin.put(f"/api/suppliers/{supplier_id}", json={"name": "Metro Wholesale"})
    assert updated.json["name"] == "Metro Wholesale"
    assert admin.get("/api/suppliers/?search=wholesale").json["count"] == 1
    assert admin.delete(f"/api/suppliers/{supplier_id}").status_code == 204
