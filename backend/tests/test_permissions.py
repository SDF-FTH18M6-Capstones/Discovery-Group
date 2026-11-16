import re
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import Asset, Category, Product, Request, Supplier

ALL = ("admin", "procurement", "inventory", "sales", "employee")
STOCK = ("admin", "inventory")
BUYING = ("admin", "procurement")

PRODUCT = {
    "sku": "SP-NEW",
    "name": "New product",
    "category_id": "{category}",
    "cost_price": "10.00",
    "selling_price": "15.00",
}
ASSET = {"asset_code": "AST-NEW", "name": "New laptop"}
REQUEST = {"item": "Printer paper", "quantity": 2, "reason": "Monthly reports"}

# method, path, roles allowed, success status, JSON body
ENDPOINTS = [
    ("GET", "/api/auth/me", ALL, 200, None),
    ("GET", "/api/users/", ("admin",), 200, None),
    ("GET", "/api/users/{other_user}", ("admin",), 200, None),
    ("PUT", "/api/users/{other_user}/role", ("admin",), 200, {"role": "sales"}),
    ("GET", "/api/categories/", ALL, 200, None),
    ("POST", "/api/categories/", STOCK, 201, {"name": "Snacks"}),
    ("GET", "/api/categories/{category}", ALL, 200, None),
    ("PUT", "/api/categories/{category}", STOCK, 200, {"name": "Drinks"}),
    ("DELETE", "/api/categories/{empty_category}", STOCK, 204, None),
    ("GET", "/api/products/", ALL, 200, None),
    ("POST", "/api/products/", STOCK, 201, PRODUCT),
    ("GET", "/api/products/{product}", ALL, 200, None),
    ("PUT", "/api/products/{product}", STOCK, 200, PRODUCT),
    ("DELETE", "/api/products/{product}", STOCK, 204, None),
    ("GET", "/api/suppliers/", BUYING, 200, None),
    ("POST", "/api/suppliers/", BUYING, 201, {"name": "Metro"}),
    ("GET", "/api/suppliers/{supplier}", BUYING, 200, None),
    ("PUT", "/api/suppliers/{supplier}", BUYING, 200, {"name": "Metro Ltd"}),
    ("DELETE", "/api/suppliers/{supplier}", BUYING, 204, None),
    ("GET", "/api/requests/", ALL, 200, None),
    ("POST", "/api/requests/", ALL, 201, REQUEST),
    ("GET", "/api/requests/{my_request}", ALL, 200, None),
    ("PUT", "/api/requests/{my_request}", ALL, 200, REQUEST),
    ("DELETE", "/api/requests/{my_request}", ALL, 204, None),
    ("POST", "/api/requests/{others_request}/approve", ("procurement",), 200, {}),
    ("POST", "/api/requests/{others_request}/reject", ("procurement",), 200, {"comment": "No"}),
    ("GET", "/api/assets/", ALL, 200, None),
    ("POST", "/api/assets/", STOCK, 201, ASSET),
    ("GET", "/api/assets/{my_asset}", ALL, 200, None),
    ("PUT", "/api/assets/{my_asset}", STOCK, 200, ASSET),
    ("DELETE", "/api/assets/{my_asset}", STOCK, 204, None),
]

# Open to everyone, by design. /refresh needs a refresh token and is tested in test_auth.py.
PUBLIC = [
    ("GET", "/api/health"),
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/refresh"),
]


def build_world(caller, make_user):
    """Create one of everything the URLs above point at, and return their ids."""
    other = make_user("employee")
    category = Category(name="Beverages")
    empty_category = Category(name="Empty")
    db.session.add_all([category, empty_category])
    db.session.flush()
    product = Product(
        sku="SP-001",
        name="Water",
        category_id=category.id,
        cost_price=Decimal("1"),
        selling_price=Decimal("2"),
    )
    supplier = Supplier(name="Nairobi Supplies")
    my_request = Request(requester_id=caller.id, item="Pens", quantity=1, reason="Out of pens")
    others_request = Request(requester_id=other.id, item="Chair", quantity=1, reason="Broken")
    my_asset = Asset(asset_code="AST-1", name="Laptop", status="assigned", assigned_to=caller.id)
    db.session.add_all([product, supplier, my_request, others_request, my_asset])
    db.session.commit()
    return {
        "other_user": other.id,
        "category": category.id,
        "empty_category": empty_category.id,
        "product": product.id,
        "supplier": supplier.id,
        "my_request": my_request.id,
        "others_request": others_request.id,
        "my_asset": my_asset.id,
    }


def fill(value, ids):
    if isinstance(value, str):
        for key, number in ids.items():
            if value == f"{{{key}}}":
                return number
            value = value.replace(f"{{{key}}}", str(number))
        return value
    if isinstance(value, dict):
        return {k: fill(v, ids) for k, v in value.items()}
    return value


def endpoint_id(endpoint):
    return f"{endpoint[0]} {endpoint[1]}"


@pytest.mark.parametrize("endpoint", ENDPOINTS, ids=endpoint_id)
def test_no_token_gets_401(client, make_user, endpoint):
    method, path, _roles, _status, body = endpoint
    ids = build_world(make_user("employee"), make_user)

    response = client.open(fill(path, ids), method=method, json=fill(body, ids))

    assert response.status_code == 401
    assert response.json["error"]["message"] == "Please sign in to continue."


@pytest.mark.parametrize("endpoint", ENDPOINTS, ids=endpoint_id)
def test_broken_token_gets_401(client, make_user, endpoint):
    method, path, _roles, _status, body = endpoint
    ids = build_world(make_user("employee"), make_user)

    response = client.open(
        fill(path, ids),
        method=method,
        json=fill(body, ids),
        headers={"Authorization": "Bearer not.a.real.token"},
    )

    assert response.status_code == 401


@pytest.mark.parametrize("role", ALL)
@pytest.mark.parametrize("endpoint", ENDPOINTS, ids=endpoint_id)
def test_each_role_gets_exactly_its_permissions(as_role, make_user, endpoint, role):
    method, path, allowed, success, body = endpoint
    caller = as_role(role)
    ids = build_world(caller.user, make_user)

    response = caller.open(method, fill(path, ids), json=fill(body, ids))

    if role in allowed:
        assert response.status_code == success, response.json
    else:
        assert response.status_code == 403
        assert response.json["error"]["message"] == "You do not have permission to do this."


def test_every_endpoint_is_listed(app):
    """Guard: a new endpoint must be added to ENDPOINTS or PUBLIC above."""

    def shape(path):
        return re.sub(r"<[^>]+>|\{[^}]+\}", "{}", path)

    in_app = {
        (method, shape(rule.rule))
        for rule in app.url_map.iter_rules()
        if rule.rule.startswith("/api/") and "openapi" not in rule.rule and "docs" not in rule.rule
        for method in rule.methods - {"HEAD", "OPTIONS"}
    }
    listed = {(m, shape(p)) for m, p, *_ in ENDPOINTS} | {(m, shape(p)) for m, p in PUBLIC}

    assert in_app - listed == set(), "These endpoints have no permission test"
    assert listed - in_app == set(), "These listed endpoints do not exist"
