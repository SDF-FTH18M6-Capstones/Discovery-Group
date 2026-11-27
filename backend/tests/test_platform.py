from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.billing import add_months, business_today
from app.extensions import db
from app.models import ROLE_CLASSES, AuditLog, Business, MpesaPayment, Notification, Sale
from app.tenancy import tenant
from tests.conftest import PASSWORD, AuthClient

OWNER_ONLY = [
    ("GET", "/api/platform/overview"),
    ("GET", "/api/platform/businesses"),
    ("GET", "/api/platform/payments"),
    ("PUT", "/api/platform/price"),
    ("POST", "/api/platform/businesses/{}/extend"),
    ("POST", "/api/platform/businesses/{}/suspend"),
    ("POST", "/api/platform/businesses/{}/reactivate"),
]
BODIES = {
    "/api/platform/price": {"price": 2000},
    "/api/platform/businesses/{}/extend": {"months": 1, "note": "Goodwill"},
    "/api/platform/businesses/{}/suspend": {"reason": "Testing"},
}


@pytest.fixture()
def owner(app, admin):
    app.config["PLATFORM_OWNERS"] = [admin.user.email]
    yield admin
    app.config["PLATFORM_OWNERS"] = []


@pytest.fixture()
def shop(app, client):
    def create(name, trial_days=10, paid_days=None, active=True, staff=("admin",)):
        business = Business(name=name, is_active=active)
        today = date.today()
        business.trial_ends_on = today + timedelta(days=trial_days)
        if paid_days is not None:
            business.paid_until = today + timedelta(days=paid_days)
        db.session.add(business)
        db.session.commit()
        people = []
        with tenant(business.id):
            for number, role in enumerate(staff):
                person = ROLE_CLASSES[role](
                    full_name=f"{name} {role}",
                    email=f"{role}{number}@{name.lower().replace(' ', '')}.test",
                    approved_at=datetime.now(UTC),
                )
                person.set_password(PASSWORD)
                db.session.add(person)
                people.append(person)
            db.session.commit()
        return business, people

    return create


def paid(business_id, amount, simulated=False, when=None):
    with tenant(business_id):
        attendant = db.session.scalar(db.select(ROLE_CLASSES["admin"].id))
        db.session.add(
            MpesaPayment(
                purpose="subscription",
                months=1,
                attendant_id=attendant,
                phone="254712345678",
                amount=amount,
                items={},
                status="paid",
                simulated=simulated,
                receipt_number=f"R{business_id}{amount}{int(simulated)}",
                checkout_request_id=f"C{business_id}{amount}{int(simulated)}",
                completed_at=when or datetime.now(UTC),
            )
        )
        db.session.commit()


@pytest.mark.parametrize(("method", "path"), OWNER_ONLY)
def test_only_stockpilot_owners_get_in(admin, client, method, path):
    url, body = path.format(1), BODIES.get(path)

    assert client.open(url, method=method, json=body).status_code == 401
    assert admin.open(method, url, json=body).status_code == 404


def test_the_account_says_who_owns_the_platform(owner, as_role):
    assert owner.get("/api/auth/me").json["platform_owner"] is True
    assert as_role("sales").get("/api/auth/me").json["platform_owner"] is False


def test_the_overview_counts_every_business(owner, shop, business):
    business.trial_ends_on = date.today() + timedelta(days=5)
    db.session.commit()
    active, _ = shop("Mama Mboga", trial_days=-20, paid_days=20)
    shop("Kibanda", trial_days=-3)
    shop("Old Shop", trial_days=-40)
    shop("Closed Shop", active=False)
    paid(active.id, 1500)
    paid(active.id, 4500, when=datetime.now(UTC) - timedelta(days=62))
    paid(active.id, 1500, simulated=True)

    overview = owner.get("/api/platform/overview").json

    assert overview["businesses"] == 5
    assert overview["by_status"] == {
        "trial": 1,
        "active": 1,
        "grace": 1,
        "expired": 1,
        "suspended": 1,
    }
    assert overview["revenue_this_month"] == 1500
    assert overview["revenue_total"] == 6000
    assert (overview["price"], overview["paybill_mode"], overview["paybill_connected"]) == (
        1500,
        "simulate",
        False,
    )


def test_businesses_list_owner_staff_and_last_sale(owner, shop):
    mboga, people = shop("Mama Mboga", staff=("admin", "sales", "sales"))
    with tenant(mboga.id):
        db.session.add(
            Sale(attendant_id=people[1].id, payment_method="cash", total=Decimal("50"), number=1)
        )
        db.session.commit()

    listing = owner.get("/api/platform/businesses?search=mboga").json

    assert listing["count"] == 1
    [row] = listing["results"]
    assert (row["name"], row["owner_email"], row["staff"], row["status"]) == (
        "Mama Mboga",
        "admin0@mamamboga.test",
        3,
        "trial",
    )
    assert row["last_sale_at"] is not None


def test_businesses_filter_by_status_and_page(owner, shop):
    for number in range(3):
        shop(f"Expired {number}", trial_days=-40)

    first = owner.get("/api/platform/businesses?status=expired&per_page=2").json
    second = owner.get("/api/platform/businesses?status=expired&per_page=2&page=2").json

    assert (first["count"], first["pages"], len(first["results"])) == (3, 2, 2)
    assert len(second["results"]) == 1
    assert all(row["status"] == "expired" for row in first["results"] + second["results"])


def test_payments_from_every_business_in_one_list(owner, shop):
    one, _ = shop("Shop One")
    two, _ = shop("Shop Two")
    paid(one.id, 1500, when=datetime.now(UTC) - timedelta(hours=2))
    paid(two.id, 4500)

    payments = owner.get("/api/platform/payments").json

    assert payments["count"] == 2
    assert [(p["business_name"], p["amount"]) for p in payments["results"]] == [
        ("Shop Two", 4500),
        ("Shop One", 1500),
    ]


def test_changing_the_price_applies_to_new_payments(owner):
    changed = owner.put("/api/platform/price", json={"price": 2000})
    started = owner.post("/api/billing/pay", json={"months": 3, "phone": "0712345678"})

    assert changed.json["price"] == 2000
    assert owner.get("/api/billing").json["price"] == 2000
    assert started.json["amount"] == 6000
    assert owner.put("/api/platform/price", json={"price": 0}).status_code == 422


def test_free_months_extend_a_business_and_tell_its_admin(owner, shop, outbox):
    mboga, people = shop("Mama Mboga", trial_days=4)
    trial_end = business_today(mboga) + timedelta(days=4)
    mboga.trial_ends_on = trial_end
    db.session.commit()

    extended = owner.post(
        f"/api/platform/businesses/{mboga.id}/extend",
        json={"months": 2, "note": "Paid in cash at the office"},
    )

    assert extended.json["paid_until"] == add_months(trial_end, 2).isoformat()
    with tenant(mboga.id):
        entry = db.session.scalar(db.select(AuditLog).where(AuditLog.action == "extended"))
        note = db.session.scalar(db.select(Notification.message))
    assert entry.summary == "StockPilot added 2 months: Paid in cash at the office"
    assert entry.user_id is None
    assert "now paid until" in note
    assert outbox[-1]["to"] == people[0].email


def test_extending_needs_a_reason(owner, shop):
    mboga, _ = shop("Mama Mboga")

    refused = owner.post(f"/api/platform/businesses/{mboga.id}/extend", json={"months": 1})

    assert refused.status_code == 422


def test_suspending_locks_a_business_out_until_reactivated(owner, shop, client, outbox):
    mboga, people = shop("Mama Mboga", staff=("admin", "sales"))
    seller = AuthClient(client, people[1])

    suspended = owner.post(
        f"/api/platform/businesses/{mboga.id}/suspend", json={"reason": "Card fraud report"}
    )
    again = owner.post(f"/api/platform/businesses/{mboga.id}/suspend", json={"reason": "Again"})
    locked_out = seller.get("/api/products/")
    sign_in = client.post("/api/auth/login", json={"email": people[1].email, "password": PASSWORD})

    assert suspended.json["status"] == "suspended"
    assert again.status_code == 409
    assert locked_out.status_code == 401
    assert sign_in.status_code == 403
    assert outbox[-1]["subject"] == "Your StockPilot account is suspended"

    back = owner.post(f"/api/platform/businesses/{mboga.id}/reactivate")

    assert back.json["is_active"] is True
    assert seller.get("/api/products/").status_code == 200
    assert owner.post(f"/api/platform/businesses/{mboga.id}/reactivate").status_code == 409


def test_owners_cannot_suspend_their_own_business(owner):
    response = owner.post(
        f"/api/platform/businesses/{owner.user.business_id}/suspend", json={"reason": "Testing"}
    )

    assert response.status_code == 409


def test_unknown_businesses_are_404(owner):
    assert owner.post("/api/platform/businesses/999/reactivate").status_code == 404
