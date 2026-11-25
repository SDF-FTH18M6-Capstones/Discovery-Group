import re
from datetime import UTC, datetime, timedelta

from app.extensions import db
from app.models import AuditLog, Business, PasswordReset, User
from tests.conftest import PASSWORD

NEW_PASSWORD = "Brand9New"


def sign_in(client, email, password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_a_new_business_signs_up_and_its_owner_is_the_administrator(client):
    response = client.post(
        "/api/auth/register-business",
        json={
            "business_name": "Mama Mboga Stores",
            "full_name": "Wanjiku Kamau",
            "email": "Wanjiku@Mboga.test",
            "password": PASSWORD,
        },
    )

    assert response.status_code == 201
    assert response.json["user"]["role"] == "admin"
    assert response.json["user"]["business"]["name"] == "Mama Mboga Stores"
    headers = bearer(response.json["access_token"])
    settings = client.get("/api/business", headers=headers).json
    assert re.fullmatch(r"[A-Z2-9]{8}", settings["join_code"])
    assert settings["currency"] == "KES"
    assert settings["vat_rate"] == "16.00"
    assert client.get("/api/products/?status=all", headers=headers).json["count"] == 0
    assert client.get("/api/users/", headers=headers).json["count"] == 1


def test_staff_join_with_the_code_and_a_wrong_code_is_refused(client, business):
    body = {"full_name": "Barclay Koin", "email": "b@test.com", "password": PASSWORD}

    wrong = client.post("/api/auth/register", json={**body, "join_code": "NOPE1234"})
    right = client.post("/api/auth/register", json={**body, "join_code": business.join_code})

    assert wrong.status_code == 422
    assert "join_code" in wrong.json["error"]["details"]
    assert right.status_code == 201
    user = db.session.scalar(db.select(User).filter_by(email="b@test.com"))
    assert (user.role, user.business_id) == ("employee", business.id)


def test_a_new_join_code_stops_the_old_one(admin, client):
    new = admin.post("/api/business/join-code").json["join_code"]
    body = {"full_name": "Late Comer", "email": "late@test.com", "password": PASSWORD}

    assert new != "TESTJOIN"
    assert (
        client.post("/api/auth/register", json={**body, "join_code": "TESTJOIN"}).status_code == 422
    )
    assert client.post("/api/auth/register", json={**body, "join_code": new}).status_code == 201


def test_only_the_admin_sees_the_join_code(as_role):
    assert as_role("admin").get("/api/business").json["join_code"] == "TESTJOIN"
    assert as_role("sales").get("/api/business").json["join_code"] is None


def test_business_settings_change_and_are_audited(admin):
    response = admin.put(
        "/api/business",
        json={
            "name": "Test Shop Ltd",
            "timezone": "Africa/Kampala",
            "currency": "UGX",
            "vat_rate": "18",
            "receipt_footer": "Thank you!",
        },
    )

    assert response.status_code == 200
    assert response.json["vat_rate"] == "18.00"
    assert admin.get("/api/auth/me").json["business"]["currency"] == "UGX"
    entry = db.session.scalar(db.select(AuditLog).filter_by(entity_type="business"))
    assert entry.changes["vat_rate"] == ["16.00", "18.00"]
    assert entry.changes["timezone"] == ["Africa/Nairobi", "Africa/Kampala"]


def test_bad_business_settings_are_422(admin):
    base = {"name": "Shop", "timezone": "Africa/Nairobi", "currency": "KES", "vat_rate": "16"}
    for field, value in [("timezone", "Mars/Base"), ("currency", "shillings"), ("vat_rate", "120")]:
        response = admin.put("/api/business", json={**base, field: value})
        assert response.status_code == 422
        assert field in response.json["error"]["details"]


def test_signing_out_ends_the_session_on_the_server(client, make_user):
    make_user("sales", email="vincent@test.com")
    session = sign_in(client, "vincent@test.com").json
    access, refresh = session["access_token"], session["refresh_token"]
    assert client.get("/api/auth/me", headers=bearer(access)).status_code == 200

    out = client.post("/api/auth/logout", headers=bearer(access))

    assert out.status_code == 200
    assert client.get("/api/auth/me", headers=bearer(access)).status_code == 401
    reused = client.post("/api/auth/refresh", headers=bearer(refresh))
    assert reused.status_code == 401
    assert reused.json["error"]["message"] == "Your session has ended. Please sign in again."


def test_signing_out_one_device_keeps_the_other(client, make_user):
    make_user("sales", email="vincent@test.com")
    phone = sign_in(client, "vincent@test.com").json
    laptop = sign_in(client, "vincent@test.com").json

    client.post("/api/auth/logout", headers=bearer(phone["refresh_token"]))

    assert (
        client.post("/api/auth/refresh", headers=bearer(phone["refresh_token"])).status_code == 401
    )
    assert client.get("/api/auth/me", headers=bearer(laptop["access_token"])).status_code == 200


def test_refreshed_access_tokens_die_with_their_session(client, make_user):
    make_user("sales", email="vincent@test.com")
    session = sign_in(client, "vincent@test.com").json
    renewed = client.post("/api/auth/refresh", headers=bearer(session["refresh_token"])).json

    client.post("/api/auth/logout", headers=bearer(session["access_token"]))

    assert client.get("/api/auth/me", headers=bearer(renewed["access_token"])).status_code == 401


def reset_link(outbox):
    return re.search(r"token=(\S+)", outbox[-1]["body"]).group(1)


def test_password_reset_by_email(client, make_user, outbox):
    make_user("employee", email="barclay@test.com")
    old_session = sign_in(client, "barclay@test.com").json

    asked = client.post("/api/auth/forgot-password", json={"email": "BARCLAY@test.com"})

    assert asked.status_code == 200
    assert outbox[-1]["to"] == "barclay@test.com"
    assert "http://localhost:5173/reset-password?token=" in outbox[-1]["body"]
    token = reset_link(outbox)

    done = client.post("/api/auth/reset-password", json={"token": token, "password": NEW_PASSWORD})
    assert done.status_code == 200
    assert sign_in(client, "barclay@test.com").status_code == 401
    assert sign_in(client, "barclay@test.com", NEW_PASSWORD).status_code == 200
    assert (
        client.get("/api/auth/me", headers=bearer(old_session["access_token"])).status_code == 401
    )
    assert (
        client.post("/api/auth/refresh", headers=bearer(old_session["refresh_token"])).status_code
        == 401
    )

    again = client.post("/api/auth/reset-password", json={"token": token, "password": "Other9Pass"})
    assert again.status_code == 400


def test_the_reset_answer_does_not_reveal_who_has_an_account(client, make_user, outbox):
    make_user("employee", email="barclay@test.com")

    known = client.post("/api/auth/forgot-password", json={"email": "barclay@test.com"})
    unknown = client.post("/api/auth/forgot-password", json={"email": "nobody@test.com"})

    assert known.json == unknown.json
    assert known.status_code == unknown.status_code == 200
    assert len(outbox) == 1


def test_an_expired_reset_link_is_refused(client, make_user, outbox):
    make_user("employee", email="barclay@test.com")
    client.post("/api/auth/forgot-password", json={"email": "barclay@test.com"})
    token = reset_link(outbox)
    reset = db.session.scalar(db.select(PasswordReset))
    reset.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.session.commit()

    response = client.post(
        "/api/auth/reset-password", json={"token": token, "password": NEW_PASSWORD}
    )

    assert response.status_code == 400
    assert "expired" in response.json["error"]["message"]


def test_a_reset_password_must_be_strong(client):
    response = client.post("/api/auth/reset-password", json={"token": "x" * 20, "password": "weak"})

    assert response.status_code == 422
    assert "password" in response.json["error"]["details"]


def test_a_deactivated_user_cannot_sign_in_and_their_session_stops(admin, client, make_user):
    seller = make_user("sales", email="vincent@test.com")
    session = sign_in(client, "vincent@test.com").json

    response = admin.post(f"/api/users/{seller.id}/deactivate")

    assert response.status_code == 200
    assert response.json["is_active"] is False
    me = client.get("/api/auth/me", headers=bearer(session["access_token"]))
    assert me.status_code == 401
    assert "deactivated" in me.json["error"]["message"]
    refused = sign_in(client, "vincent@test.com")
    assert refused.status_code == 403
    assert (
        client.post("/api/auth/forgot-password", json={"email": "vincent@test.com"}).status_code
        == 200
    )

    admin.post(f"/api/users/{seller.id}/reactivate")
    assert sign_in(client, "vincent@test.com").status_code == 200


def test_deactivated_users_leave_the_holder_list_but_keep_history(admin, make_user):
    seller = make_user("sales")
    admin.post(f"/api/users/{seller.id}/deactivate")

    choices = [u["id"] for u in admin.get("/api/users/choices").json]
    listed = admin.get("/api/users/?active=false").json["results"]

    assert seller.id not in choices
    assert [u["id"] for u in listed] == [seller.id]


def test_the_admin_cannot_deactivate_themselves(admin):
    response = admin.post(f"/api/users/{admin.user.id}/deactivate")

    assert response.status_code == 409


def test_role_changes_and_deactivation_are_in_the_audit_log(admin, make_user):
    user_id = make_user("employee", full_name="Barclay Koin").id
    admin.put(f"/api/users/{user_id}/role", json={"role": "sales"})
    admin.post(f"/api/users/{user_id}/deactivate")

    log = admin.get("/api/audit/?entity_type=user").json["results"]

    assert [(e["action"], e["summary"]) for e in log] == [
        ("deactivated", "Barclay Koin deactivated"),
        ("role_changed", "Barclay Koin: Employee → Sales Attendant"),
    ]
    assert log[0]["user_name"] == admin.user.full_name


def test_profile_phone_can_be_saved(as_role):
    me = as_role("employee")

    response = me.put("/api/auth/me", json={"full_name": "New Name", "phone": "+254 712 345678"})
    bad = me.put("/api/auth/me", json={"full_name": "New Name", "phone": "call me"})

    assert response.json["phone"] == "+254 712 345678"
    assert bad.status_code == 422


def test_a_suspended_business_cannot_sign_in(client, make_user, business):
    make_user("admin", email="boss@test.com")
    business_row = db.session.get(Business, business.id)
    business_row.is_active = False
    db.session.commit()

    assert sign_in(client, "boss@test.com").status_code == 403
