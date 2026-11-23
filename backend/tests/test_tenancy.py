import pytest

from app.extensions import db
from app.models import ROLE_CLASSES, Business, Product, StockMovement
from app.tenancy import tenant
from tests.conftest import PASSWORD, AuthClient
from tests.test_permissions import ENDPOINTS, build_world, endpoint_id, fill

LISTS = [
    "/api/users/",
    "/api/users/choices",
    "/api/categories/",
    "/api/products/?status=all",
    "/api/suppliers/",
    "/api/requests/",
    "/api/assets/",
    "/api/asset-categories/",
    "/api/sales/",
    "/api/purchases/",
    "/api/stock/movements",
    "/api/repairs/",
    "/api/notifications/",
    "/api/expenses/",
    "/api/audit/",
]


@pytest.fixture()
def other_business(app):
    business = Business(name="Other Shop", join_code="OTHERJN1")
    db.session.add(business)
    db.session.commit()
    with tenant(business.id):
        counter = {"n": 0}

        def make_user(role="employee", **_):
            counter["n"] += 1
            user = ROLE_CLASSES[role](
                full_name=f"Other {role} {counter['n']}", email=f"other{counter['n']}@other.test"
            )
            user.set_password(PASSWORD)
            db.session.add(user)
            db.session.commit()
            return user

        owner = make_user("admin")
        ids = build_world(owner, make_user)
        ids["owner"] = owner.id
    return business, ids


def counts(client):
    result = {}
    for url in LISTS:
        body = client.get(url).json
        result[url] = len(body) if isinstance(body, list) else body["count"]
    return result


def test_lists_never_include_another_business(admin, make_user, other_business):
    build_world(admin.user, make_user)
    db.session.expire_all()
    mine = counts(admin)

    business, _ = other_business
    with tenant(business.id):
        theirs = db.session.scalar(db.select(db.func.count(Product.id)))
    assert theirs == mine["/api/products/?status=all"] > 0
    assert counts(admin) == mine


@pytest.mark.parametrize("endpoint", [e for e in ENDPOINTS if "{" in e[1]], ids=endpoint_id)
def test_another_business_records_are_not_found(as_role, make_user, other_business, endpoint):
    method, path, allowed, _success, body = endpoint
    _, theirs = other_business
    caller = as_role(allowed[0])
    mine = build_world(caller.user, make_user)
    if "{asset_code}" in path:
        path = path.replace("{asset_code}", "SP9999000001")  # a barcode that is not ours

    response = caller.open(method, fill(path, theirs), json=fill(body, mine))

    assert response.status_code == 404, (path, response.json)


def test_ids_from_another_business_cannot_be_used_in_a_body(as_role, make_user, other_business):
    _, theirs = other_business
    admin = as_role("admin")
    mine = build_world(admin.user, make_user)
    seller, buyer, store = as_role("sales"), as_role("procurement"), as_role("inventory")

    sale = seller.post(
        "/api/sales/",
        json={
            "payment_method": "cash",
            "items": [{"product_id": theirs["product"], "quantity": 1}],
        },
    )
    order = buyer.post(
        "/api/purchases/",
        json={
            "supplier_id": theirs["supplier"],
            "items": [{"product_id": mine["product"], "quantity": 1, "unit_cost": "1"}],
        },
    )
    product = admin.post(
        "/api/products/",
        json={
            "sku": "X-1",
            "name": "X",
            "category_id": theirs["category"],
            "cost_price": "1",
            "selling_price": "2",
        },
    )
    adjust = store.post(
        "/api/stock/adjustments",
        json={"product_id": theirs["product"], "change": 1, "reason": "Recount"},
    )
    assign = store.post(
        f"/api/assets/{mine['free_asset']}/assign",
        json={"user_id": theirs["owner"], "condition": "good"},
    )
    repair = store.post(
        "/api/repairs/", json={"asset_id": theirs["my_asset"], "description": "Broken screen"}
    )
    request = admin.post(
        "/api/requests/",
        json={"item": "Water", "quantity": 1, "reason": "Need", "product_id": theirs["product"]},
    )

    for response in (sale, order, product, adjust, assign, repair, request):
        assert response.status_code == 400, response.json
    with tenant(other_business[0].id):
        assert db.session.scalar(db.select(db.func.count(StockMovement.id))) == 0


def test_reports_and_pulse_count_only_this_business(as_role, make_user, other_business):
    business, theirs = other_business
    with tenant(business.id):
        owner = db.session.get(ROLE_CLASSES["admin"], theirs["owner"])
        AuthClient(as_role("admin").client, owner).post(
            "/api/sales/",
            json={
                "payment_method": "cash",
                "items": [{"product_id": theirs["product"], "quantity": 5}],
            },
        )
    admin = as_role("admin")

    report = admin.get("/api/reports/summary?days=1").json
    pulse = {t["key"]: t["count"] for t in admin.get("/api/dashboard/pulse").json["tiles"]}

    assert report["sales_count"] == 0
    assert report["sales_total"] == "0.00"
    assert report["stock_value"] == "0.00"
    assert pulse == {
        "low_stock": 0,
        "approvals": 0,
        "awaiting_receipt": 0,
        "open_repairs": 0,
        "sales_today": 0,
    }


def test_document_numbers_start_at_one_in_every_business(as_role, make_user, other_business):
    admin = as_role("admin")
    created = admin.post("/api/suppliers/", json={"name": "Metro"}).json
    assert created["code"] == "SUP-001" 


def test_the_same_sku_and_email_rules(as_role, make_user, other_business, client):
    admin = as_role("admin")
    category = admin.post("/api/categories/", json={"name": "Beverages"}).json["id"]
    body = {
        "sku": "SP-001", 
        "name": "Water",
        "category_id": category,
        "cost_price": "1",
        "selling_price": "2",
    }
    assert admin.post("/api/products/", json=body).status_code == 201

    taken = client.post(
        "/api/auth/register",
        json={
            "full_name": "Someone",
            "email": "other1@other.test",
            "password": PASSWORD,
            "join_code": "TESTJOIN",
        },
    )
    assert taken.status_code == 409


def test_signing_in_puts_you_in_your_own_business(client, other_business):
    response = client.post(
        "/api/auth/login", json={"email": "other1@other.test", "password": PASSWORD}
    )

    assert response.status_code == 200
    assert response.json["user"]["business"]["name"] == "Other Shop"
    headers = {"Authorization": f"Bearer {response.json['access_token']}"}
    assert client.get("/api/products/?status=all", headers=headers).json["count"] == 2
