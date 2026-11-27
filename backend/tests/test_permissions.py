import re
from datetime import date
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import (
    Asset,
    AssetAssignment,
    AssetCategory,
    Category,
    Expense,
    MpesaPayment,
    Notification,
    Product,
    Purchase,
    PurchaseItem,
    Repair,
    Request,
    Sale,
    Supplier,
)

ALL = ("admin", "procurement", "inventory", "sales", "employee")
STOCK = ("inventory",)
STOCK_VIEW = ("admin", "inventory")
BUYING = ("procurement",)
SUPPLIER_VIEW = ("admin", "procurement", "inventory")
SELLING = ("sales",)
SALES_VIEW = ("admin", "sales")
PURCHASE_VIEW = ("admin", "procurement", "inventory")
PRODUCT_CREATE = ("inventory", "procurement")

PRODUCT = {
    "sku": "SP-NEW",
    "name": "New product",
    "category_id": "{category}",
    "cost_price": "10.00",
    "selling_price": "15.00",
}
ASSET = {"name": "New laptop"}
REQUEST = {"item": "Printer paper", "quantity": 2, "reason": "Monthly reports"}
SALE = {"payment_method": "cash", "items": [{"product_id": "{product}", "quantity": 1}]}
PURCHASE = {
    "supplier_id": "{supplier}",
    "items": [{"product_id": "{product}", "quantity": 5, "unit_cost": "1.00"}],
}
REPAIR = {"asset_id": "{spare_asset}", "description": "Screen flickers"}
ADJUSTMENT = {"product_id": "{product}", "change": -1, "reason": "Damaged in store"}
BUSINESS = {"name": "Test Shop", "timezone": "Africa/Nairobi", "currency": "KES", "vat_rate": "16"}
EXPENSE = {"spent_on": "2026-11-01", "category": "Rent", "amount": "1000.00"}
ASSIGN = {"user_id": "{other_user}", "condition": "good"}
ENDPOINTS = [
    ("GET", "/api/auth/me", ALL, 200, None),
    ("GET", "/api/users/", ("admin",), 200, None),
    ("GET", "/api/users/choices", ("admin", "inventory"), 200, None),
    ("GET", "/api/users/{other_user}", ("admin",), 200, None),
    ("PUT", "/api/users/{other_user}/role", ("admin",), 200, {"role": "sales"}),
    ("POST", "/api/users/{other_user}/deactivate", ("admin",), 200, None),
    ("POST", "/api/users/{other_user}/reactivate", ("admin",), 200, None),
    ("POST", "/api/users/{waiting_user}/approve", ("admin",), 200, {"role": "sales"}),
    ("POST", "/api/users/{waiting_user}/decline", ("admin",), 204, None),
    ("GET", "/api/business", ALL, 200, None),
    ("PUT", "/api/business", ("admin",), 200, BUSINESS),
    ("POST", "/api/business/join-code", ("admin",), 200, None),
    ("GET", "/api/audit/", ("admin",), 200, None),
    ("GET", "/api/dashboard/pulse", ALL, 200, None),
    ("GET", "/api/expenses/", ("admin",), 200, None),
    ("POST", "/api/expenses/", ("admin",), 201, EXPENSE),
    ("PUT", "/api/expenses/{expense}", ("admin",), 200, EXPENSE),
    ("DELETE", "/api/expenses/{expense}", ("admin",), 204, None),
    ("GET", "/api/categories/", ALL, 200, None),
    ("POST", "/api/categories/", STOCK, 201, {"name": "Snacks"}),
    ("GET", "/api/categories/{category}", ALL, 200, None),
    ("PUT", "/api/categories/{category}", STOCK, 200, {"name": "Drinks"}),
    ("DELETE", "/api/categories/{empty_category}", STOCK, 204, None),
    ("GET", "/api/products/", ALL, 200, None),
    ("POST", "/api/products/", PRODUCT_CREATE, 201, PRODUCT),
    ("GET", "/api/products/{product}", ALL, 200, None),
    ("PUT", "/api/products/{product}", STOCK, 200, PRODUCT),
    ("DELETE", "/api/products/{spare_product}", STOCK, 204, None),
    ("POST", "/api/products/{product}/retire", STOCK, 200, None),
    ("POST", "/api/products/{product}/restore", STOCK, 200, None),
    ("POST", "/api/products/{product}/photo", STOCK, 400, None),
    ("DELETE", "/api/products/{product}/photo", STOCK, 200, None),
    ("GET", "/api/products/{product}/timeline", STOCK_VIEW, 200, None),
    ("GET", "/api/suppliers/", SUPPLIER_VIEW, 200, None),
    ("POST", "/api/suppliers/", BUYING, 201, {"name": "Metro"}),
    ("GET", "/api/suppliers/{supplier}", SUPPLIER_VIEW, 200, None),
    ("PUT", "/api/suppliers/{supplier}", BUYING, 200, {"name": "Metro Ltd"}),
    ("DELETE", "/api/suppliers/{spare_supplier}", BUYING, 204, None),
    ("GET", "/api/requests/", ALL, 200, None),
    ("POST", "/api/requests/", ALL, 201, REQUEST),
    ("GET", "/api/requests/{my_request}", ALL, 200, None),
    ("PUT", "/api/requests/{my_request}", ALL, 200, REQUEST),
    ("DELETE", "/api/requests/{my_request}", ALL, 204, None),
    ("POST", "/api/requests/{my_request}/cancel", ALL, 200, None),
    ("GET", "/api/requests/{my_request}/timeline", ALL, 200, None),
    ("POST", "/api/requests/{approved_request}/fulfil", BUYING, 200, None),
    ("POST", "/api/requests/{others_request}/approve", ("procurement",), 200, {}),
    ("POST", "/api/requests/{others_request}/reject", ("procurement",), 200, {"comment": "No"}),
    ("GET", "/api/assets/", ALL, 200, None),
    ("POST", "/api/assets/", STOCK, 201, ASSET),
    ("GET", "/api/assets/{my_asset}", ALL, 200, None),
    ("PUT", "/api/assets/{my_asset}", STOCK, 200, ASSET),
    ("DELETE", "/api/assets/{spare_asset}", STOCK, 204, None),
    ("GET", "/api/assets/lookup/{asset_code}", STOCK_VIEW, 200, None),
    ("POST", "/api/assets/{free_asset}/assign", STOCK, 200, ASSIGN),
    ("POST", "/api/assets/{my_asset}/return", STOCK, 200, {"condition": "good"}),
    ("POST", "/api/assets/{free_asset}/retire", STOCK, 200, None),
    ("GET", "/api/assets/{my_asset}/assignments", ALL, 200, None),
    ("GET", "/api/assets/{my_asset}/timeline", ALL, 200, None),
    ("POST", "/api/assets/{my_asset}/photo", STOCK, 400, None),
    ("DELETE", "/api/assets/{my_asset}/photo", STOCK, 200, None),
    ("GET", "/api/asset-categories/", ALL, 200, None),
    ("POST", "/api/asset-categories/", STOCK, 201, {"name": "Furniture"}),
    ("PUT", "/api/asset-categories/{asset_category}", STOCK, 200, {"name": "Computers"}),
    ("DELETE", "/api/asset-categories/{asset_category}", STOCK, 204, None),
    ("GET", "/api/sales/", SALES_VIEW, 200, None),
    ("POST", "/api/sales/", SELLING, 201, SALE),
    ("GET", "/api/sales/{my_sale}", SALES_VIEW, 200, None),
    ("POST", "/api/sales/{my_sale}/void", SELLING, 200, {"reason": "Rang up twice"}),
    ("GET", "/api/payments/mpesa/config", ALL, 200, None),
    ("GET", "/api/business/mpesa", ("admin",), 200, None),
    ("PUT", "/api/business/mpesa", ("admin",), 200, {"mode": "simulate", "type": "paybill"}),
    ("GET", "/api/billing", ("admin",), 200, None),
    ("POST", "/api/billing/pay", ("admin",), 201, {"months": 1, "phone": "0712345678"}),
    ("GET", "/api/billing/payments/{my_subscription}", ("admin",), 200, None),
    (
        "POST",
        "/api/billing/payments/{my_subscription}/simulate",
        ("admin",),
        200,
        {"outcome": "cancelled"},
    ),
    (
        "POST",
        "/api/payments/mpesa",
        SELLING,
        201,
        {
            "phone": "0712345678",
            "items": [{"product_id": "{product}", "quantity": 1}],
            "idempotency_key": "permission-check",
        },
    ),
    ("GET", "/api/payments/mpesa/{my_payment}", SALES_VIEW, 200, None),
    ("POST", "/api/payments/mpesa/{my_payment}/simulate", SELLING, 200, {"outcome": "cancelled"}),
    ("GET", "/api/purchases/", PURCHASE_VIEW, 200, None),
    ("POST", "/api/purchases/", BUYING, 201, PURCHASE),
    ("GET", "/api/purchases/{purchase}", PURCHASE_VIEW, 200, None),
    ("PUT", "/api/purchases/{draft}", BUYING, 200, PURCHASE),
    ("POST", "/api/purchases/{draft}/confirm", BUYING, 200, None),
    ("POST", "/api/purchases/{purchase}/receive", STOCK, 200, {}),
    ("POST", "/api/purchases/{purchase}/cancel", BUYING, 200, {"reason": "Supplier closed"}),
    ("GET", "/api/stock/movements", STOCK_VIEW, 200, None),
    ("GET", "/api/stock/movements.csv", STOCK_VIEW, 200, None),
    ("POST", "/api/stock/adjustments", STOCK, 201, ADJUSTMENT),
    ("GET", "/api/repairs/", ALL, 200, None),
    ("POST", "/api/repairs/", ALL, 201, REPAIR),
    ("GET", "/api/repairs/{my_repair}", ALL, 200, None),
    ("PUT", "/api/repairs/{my_repair}/status", STOCK, 200, {"status": "in_progress"}),
    ("GET", "/api/repairs/{my_repair}/timeline", ALL, 200, None),
    ("GET", "/api/notifications/", ALL, 200, None),
    ("POST", "/api/notifications/{my_notification}/read", ALL, 200, None),
    ("POST", "/api/notifications/read-all", ALL, 200, None),
    ("GET", "/api/reports/summary", ("admin",), 200, None),
    ("PUT", "/api/auth/me", ALL, 200, {"full_name": "New Name"}),
    ("POST", "/api/auth/logout", ALL, 200, None),
    (
        "POST",
        "/api/auth/password",
        ALL,
        200,
        {"current_password": "Secret123!", "new_password": "NewSecret123"},
    ),
]
PUBLIC = [
    ("GET", "/api/health"),
    ("GET", "/api/images/{}"),
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/register-business"),
    ("POST", "/api/auth/forgot-password"),
    ("POST", "/api/auth/login/verify"),
    ("POST", "/api/auth/login/resend"),
    ("POST", "/api/auth/verify-email"),
    ("POST", "/api/auth/resend-verification"),
    ("POST", "/api/auth/reset-password"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/refresh"),
    ("POST", "/api/payments/mpesa/callback/{}"),
    ("POST", "/api/tasks/daily-summary"),
]


def build_world(caller, make_user):
    other = make_user("employee")
    for job in ("procurement", "inventory", "sales"):
        if caller.role != job:
            make_user(job)
    waiting = make_user("employee", approved=False)
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
        quantity=50,
    )
    supplier = Supplier(name="Nairobi Supplies")
    spare_supplier = Supplier(name="Unused Supplier")
    spare_product = Product(
        sku="SP-SPARE",
        name="Unused",
        category_id=category.id,
        cost_price=Decimal("1"),
        selling_price=Decimal("2"),
    )
    my_request = Request(requester_id=caller.id, item="Pens", quantity=1, reason="Out of pens")
    others_request = Request(requester_id=other.id, item="Chair", quantity=1, reason="Broken")
    approved_request = Request(
        requester_id=other.id, item="Desk", quantity=1, reason="New hire", status="approved"
    )
    my_asset = Asset(name="Laptop", status="assigned", assigned_to=caller.id)
    spare_asset = Asset(name="Phone", status="assigned", assigned_to=caller.id)
    free_asset = Asset(name="Projector")
    asset_category = AssetCategory(name="Gadgets")
    db.session.add_all(
        [
            product,
            supplier,
            spare_supplier,
            spare_product,
            my_request,
            others_request,
            my_asset,
            spare_asset,
            free_asset,
            asset_category,
            approved_request,
        ]
    )
    db.session.flush()
    db.session.add(
        AssetAssignment(
            asset_id=my_asset.id, user_id=caller.id, assigned_by=caller.id, condition_out="good"
        )
    )
    my_sale = Sale(attendant_id=caller.id, payment_method="cash", total=Decimal("2"))
    purchase = Purchase(
        supplier_id=supplier.id, created_by=caller.id, total=Decimal("5"), status="ordered"
    )
    purchase.items.append(PurchaseItem(product_id=product.id, quantity=5, unit_cost=Decimal("1")))
    draft = Purchase(supplier_id=supplier.id, created_by=caller.id, total=Decimal("5"))
    draft.items.append(PurchaseItem(product_id=product.id, quantity=5, unit_cost=Decimal("1")))
    expense = Expense(
        spent_on=date(2026, 11, 1), category="Rent", amount=Decimal("100"), created_by=caller.id
    )
    my_repair = Repair(asset_id=my_asset.id, reported_by=caller.id, description="Broken hinge")
    my_notification = Notification(user_id=caller.id, message="Welcome")
    my_payment = MpesaPayment(
        attendant_id=caller.id,
        phone="254712345678",
        amount=2,
        items={str(product.id): 1},
        simulated=True,
        checkout_request_id=f"SIM-permissions-{caller.id}",
    )
    my_subscription = MpesaPayment(
        purpose="subscription",
        months=1,
        attendant_id=caller.id,
        phone="254712345678",
        amount=1500,
        items={},
        simulated=True,
        checkout_request_id=f"SIM-subscription-{caller.id}",
    )
    db.session.add_all(
        [my_sale, purchase, draft, expense, my_repair, my_notification, my_payment, my_subscription]
    )
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
        "my_sale": my_sale.id,
        "my_payment": my_payment.id,
        "my_subscription": my_subscription.id,
        "spare_product": spare_product.id,
        "spare_asset": spare_asset.id,
        "my_repair": my_repair.id,
        "my_notification": my_notification.id,
        "spare_supplier": spare_supplier.id,
        "purchase": purchase.id,
        "draft": draft.id,
        "asset_code": my_asset.asset_code,
        "expense": expense.id,
        "free_asset": free_asset.id,
        "asset_category": asset_category.id,
        "approved_request": approved_request.id,
        "waiting_user": waiting.id,
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
    if isinstance(value, list):
        return [fill(v, ids) for v in value]
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
        message = response.json["error"]["message"]
        if role == "admin":
            assert "As Administrator you can follow it, but not do it." in message
        else:
            assert message == "You do not have permission to do this."


def test_every_endpoint_is_listed(app):

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
