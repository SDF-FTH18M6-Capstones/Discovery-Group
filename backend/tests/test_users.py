from app.extensions import db
from app.models import ProcurementManager, User


def test_admin_lists_and_filters_users(admin, make_user):
    make_user("sales")
    make_user("sales")

    body = admin.get("/api/users/?role=sales").json

    assert body["count"] == 2
    assert {u["role"] for u in body["results"]} == {"sales"}
    assert "password_hash" not in body["results"][0]


def test_role_change_switches_the_user_class(admin, employee):
    user_id = employee.id

    response = admin.put(f"/api/users/{user_id}/role", json={"role": "procurement"})

    assert response.status_code == 200
    assert response.json["role"] == "procurement"
    db.session.expunge_all()
    assert isinstance(db.session.get(User, user_id), ProcurementManager)


def test_new_role_applies_to_the_next_request(admin, client, employee):
    from flask_jwt_extended import create_access_token

    headers = {"Authorization": f"Bearer {create_access_token(identity=employee)}"}
    assert client.get("/api/suppliers/", headers=headers).status_code == 403

    admin.put(f"/api/users/{employee.id}/role", json={"role": "procurement"})

    assert client.get("/api/suppliers/", headers=headers).status_code == 200


def test_admin_cannot_change_their_own_role(admin):
    response = admin.put(f"/api/users/{admin.user.id}/role", json={"role": "employee"})

    assert response.status_code == 409


def test_unknown_role_is_422(admin, employee):
    response = admin.put(f"/api/users/{employee.id}/role", json={"role": "superuser"})

    assert response.status_code == 422
    assert "role" in response.json["error"]["details"]


def test_choices_list_names_for_asset_assignment_without_emails(as_role, employee):
    response = as_role("inventory").get("/api/users/choices")

    assert response.status_code == 200
    names = {row["full_name"] for row in response.json}
    assert employee.full_name in names 
    assert all(set(row) == {"id", "full_name", "role"} for row in response.json)
