"""Wrong data on every endpoint returns the right status code and a clear JSON error.

  422  a field is missing, the wrong type, out of range or unknown (Marshmallow)
  400  a field points at something that does not exist, or the body is not JSON
  404  the record does not exist
  409  the data clashes with what is already stored
  405  the method is not allowed on that URL
Every error has the same shape: {"error": {"code": ..., "message": ..., "details"?: ...}}
"""

from decimal import Decimal

import pytest

from app.extensions import db
from app.models import Product, Request

LISTS = [
    "/api/categories/",
    "/api/products/",
    "/api/suppliers/",
    "/api/requests/",
    "/api/assets/",
    "/api/users/",
]

ONE_ITEM = [
    ("GET", "/api/categories/999999"),
    ("PUT", "/api/categories/999999"),
    ("DELETE", "/api/categories/999999"),
    ("GET", "/api/products/999999"),
    ("PUT", "/api/products/999999"),
    ("DELETE", "/api/products/999999"),
    ("GET", "/api/suppliers/999999"),
    ("PUT", "/api/suppliers/999999"),
    ("DELETE", "/api/suppliers/999999"),
    ("GET", "/api/requests/999999"),
    ("PUT", "/api/requests/999999"),
    ("DELETE", "/api/requests/999999"),
    ("GET", "/api/assets/999999"),
    ("PUT", "/api/assets/999999"),
    ("DELETE", "/api/assets/999999"),
    ("GET", "/api/users/999999"),
    ("PUT", "/api/users/999999/role"),
]

VALID = {
    "/api/categories/": {"name": "Snacks"},
    "/api/products/": {
        "sku": "SP-1",
        "name": "Tea",
        "category_id": 1,
        "cost_price": "1.00",
        "selling_price": "2.00",
    },
    "/api/suppliers/": {"name": "Metro"},
    "/api/requests/": {"item": "Pens", "quantity": 1, "reason": "Out of pens"},
    "/api/assets/": {"asset_code": "AST-1", "name": "Laptop"},
    "/api/users/999999/role": {"role": "sales"},
}

# endpoint, bad body, fields that must be named in the error details
BAD_BODIES = [
    ("/api/categories/", {}, ["name"]),
    ("/api/categories/", {"name": ""}, ["name"]),
    ("/api/categories/", {"name": "x" * 101}, ["name"]),
    ("/api/categories/", {"name": 123}, ["name"]),
    ("/api/products/", {}, ["sku", "name", "category_id", "cost_price", "selling_price"]),
    ("/api/products/", {**VALID["/api/products/"], "cost_price": "-1"}, ["cost_price"]),
    ("/api/products/", {**VALID["/api/products/"], "selling_price": "abc"}, ["selling_price"]),
    ("/api/products/", {**VALID["/api/products/"], "quantity": -5}, ["quantity"]),
    ("/api/products/", {**VALID["/api/products/"], "quantity": "many"}, ["quantity"]),
    ("/api/products/", {**VALID["/api/products/"], "reorder_level": -1}, ["reorder_level"]),
    ("/api/products/", {**VALID["/api/products/"], "category_id": "one"}, ["category_id"]),
    ("/api/products/", {**VALID["/api/products/"], "image_url": "not a url"}, ["image_url"]),
    ("/api/products/", {**VALID["/api/products/"], "sku": "x" * 41}, ["sku"]),
    ("/api/products/", {**VALID["/api/products/"], "is_low_stock": True}, ["is_low_stock"]),
    ("/api/suppliers/", {}, ["name"]),
    ("/api/suppliers/", {"name": "Metro", "email": "not-an-email"}, ["email"]),
    ("/api/suppliers/", {"name": "Metro", "phone": "call me"}, ["phone"]),
    ("/api/requests/", {}, ["item", "quantity", "reason"]),
    ("/api/requests/", {**VALID["/api/requests/"], "quantity": 0}, ["quantity"]),
    ("/api/requests/", {**VALID["/api/requests/"], "urgency": "asap"}, ["urgency"]),
    ("/api/requests/", {**VALID["/api/requests/"], "status": "approved"}, ["status"]),
    ("/api/requests/", {**VALID["/api/requests/"], "requester_id": 1}, ["requester_id"]),
    ("/api/assets/", {}, ["asset_code", "name"]),
    ("/api/assets/", {**VALID["/api/assets/"], "status": "lost"}, ["status"]),
    ("/api/assets/", {**VALID["/api/assets/"], "status": "assigned"}, ["assigned_to"]),
    ("/api/assets/", {**VALID["/api/assets/"], "assigned_to": 1}, ["assigned_to"]),
]


def assert_error_shape(response, code):
    assert response.status_code == code, response.json
    assert response.is_json
    assert response.json["error"]["code"] == code
    assert response.json["error"]["message"]


@pytest.mark.parametrize("url", LISTS)
@pytest.mark.parametrize("query", ["page=0", "per_page=0", "per_page=101", "page=abc"])
def test_bad_page_numbers_are_422_on_every_list(admin, url, query):
    response = admin.get(f"{url}?{query}")

    assert_error_shape(response, 422)
    assert set(response.json["error"]["details"]) & {"page", "per_page"}


@pytest.mark.parametrize("url", LISTS)
def test_every_list_is_paginated(admin, url):
    body = admin.get(f"{url}?page=1&per_page=5").json

    assert set(body) == {"results", "count", "page", "per_page", "pages"}
    assert body["per_page"] == 5


@pytest.mark.parametrize("method, url", ONE_ITEM, ids=lambda x: str(x))
def test_missing_record_is_404_on_every_item_endpoint(admin, method, url):
    body = VALID.get("/api/users/999999/role") if url.endswith("/role") else None
    if method == "PUT" and body is None:
        body = VALID[url.rsplit("/", 1)[0] + "/"]

    response = admin.open(method, url, json=body)

    assert_error_shape(response, 404)


@pytest.mark.parametrize("url, body, fields", BAD_BODIES, ids=lambda x: str(x)[:40])
def test_invalid_fields_are_422_and_named(admin, category, url, body, fields):
    response = admin.post(url, json=body)

    assert_error_shape(response, 422)
    assert response.json["error"]["message"] == "Some fields are invalid."
    for field in fields:
        assert field in response.json["error"]["details"], response.json


@pytest.mark.parametrize("url", list(VALID)[:5])
def test_body_that_is_not_json_is_rejected(admin, url):
    response = admin.post(url, data="name=Snacks", content_type="text/plain")

    assert response.status_code in (400, 415, 422)
    assert response.is_json and "error" in response.json


def test_broken_json_is_rejected(admin):
    response = admin.post(
        "/api/categories/", data='{"name": "Snacks"', content_type="application/json"
    )

    assert response.status_code == 400
    assert "error" in response.json


def test_unknown_category_is_400(admin):
    response = admin.post("/api/products/", json={**VALID["/api/products/"], "category_id": 999})

    assert_error_shape(response, 400)


def test_unknown_asset_holder_is_400(admin):
    body = {"asset_code": "AST-9", "name": "Laptop", "status": "assigned", "assigned_to": 999}

    assert_error_shape(admin.post("/api/assets/", json=body), 400)


# ---------- 409 conflicts ----------


def test_duplicate_category_name_is_409(admin):
    admin.post("/api/categories/", json={"name": "Snacks"})

    assert_error_shape(admin.post("/api/categories/", json={"name": "Snacks"}), 409)


def test_duplicate_sku_is_409(admin, category):
    body = {**VALID["/api/products/"], "category_id": category.id}
    admin.post("/api/products/", json=body)

    assert_error_shape(admin.post("/api/products/", json=body), 409)


def test_duplicate_asset_code_is_409(admin):
    admin.post("/api/assets/", json=VALID["/api/assets/"])

    assert_error_shape(admin.post("/api/assets/", json=VALID["/api/assets/"]), 409)


def test_renaming_a_category_to_an_existing_name_is_409(admin):
    first = admin.post("/api/categories/", json={"name": "Snacks"}).json["id"]
    admin.post("/api/categories/", json={"name": "Drinks"})

    assert_error_shape(admin.put(f"/api/categories/{first}", json={"name": "Drinks"}), 409)


def test_deleting_a_category_that_has_products_is_409(admin, category):
    product = Product(
        sku="SP-9",
        name="Tea",
        category_id=category.id,
        cost_price=Decimal("1"),
        selling_price=Decimal("2"),
    )
    db.session.add(product)
    db.session.commit()

    assert_error_shape(admin.delete(f"/api/categories/{category.id}"), 409)


def test_editing_a_decided_request_is_409(as_role):
    employee = as_role("employee")
    request = Request(
        requester_id=employee.user.id, item="Pens", quantity=1, reason="x", status="approved"
    )
    db.session.add(request)
    db.session.commit()

    response = employee.put(f"/api/requests/{request.id}", json=VALID["/api/requests/"])

    assert_error_shape(response, 409)


def test_wrong_method_is_405_json(admin):
    response = admin.open("PATCH", "/api/products/")

    assert_error_shape(response, 405)


def test_unknown_url_is_404_json(client):
    assert_error_shape(client.get("/api/does-not-exist"), 404)
