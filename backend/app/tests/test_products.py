def product_data(category_id, **overrides):
    data = {
        "sku": "SP-001",
        "name": "Water Bottle 1L",
        "category_id": category_id,
        "cost_price": "180.00",
        "selling_price": "250.00",
        "quantity": 10,
        "reorder_level": 20,
    }
    data.update(overrides)
    return data


def test_full_crud_cycle(client, category):
    created = client.post("/api/products/", json=product_data(category.id))
    assert created.status_code == 201
    product_id = created.json["id"]
    assert created.json["category_name"] == "Beverages"
    assert created.json["is_low_stock"] is True

    assert client.get(f"/api/products/{product_id}").json["sku"] == "SP-001"

    updated = client.put(
        f"/api/products/{product_id}", json=product_data(category.id, selling_price="300.00")
    )
    assert updated.status_code == 200
    assert updated.json["selling_price"] == "300.00"

    assert client.delete(f"/api/products/{product_id}").status_code == 204
    assert client.get(f"/api/products/{product_id}").status_code == 404


def test_invalid_data_is_rejected_with_field_errors(client, category):
    response = client.post(
        "/api/products/", json={"sku": "", "category_id": category.id, "cost_price": "-5"}
    )

    assert response.status_code == 422
    details = response.json["error"]["details"]
    assert {"sku", "name", "cost_price", "selling_price"} <= set(details)


def test_duplicate_sku_returns_409(client, category):
    client.post("/api/products/", json=product_data(category.id))
    response = client.post("/api/products/", json=product_data(category.id, name="Other"))

    assert response.status_code == 409
    assert "SP-001" in response.json["error"]["message"]


def test_unknown_category_returns_400(client):
    response = client.post("/api/products/", json=product_data(999))

    assert response.status_code == 400


def test_list_is_paginated_and_searchable(client, category):
    for n in range(25):
        client.post(
            "/api/products/", json=product_data(category.id, sku=f"SP-{n:03}", name=f"Item {n}")
        )

    first_page = client.get("/api/products/?per_page=10").json
    assert first_page["count"] == 25
    assert first_page["pages"] == 3
    assert len(first_page["results"]) == 10

    found = client.get("/api/products/?search=SP-007").json
    assert found["count"] == 1


def test_per_page_above_100_is_rejected(client):
    assert client.get("/api/products/?per_page=500").status_code == 422


def test_category_with_products_cannot_be_deleted(client, category):
    client.post(
        "/api/products/",
        json={
            "sku": "SP-1",
            "name": "Tea",
            "category_id": category.id,
            "cost_price": "1",
            "selling_price": "2",
        },
    )

    assert client.delete(f"/api/categories/{category.id}").status_code == 409