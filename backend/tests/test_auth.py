from datetime import timedelta

import pytest
from flask_jwt_extended import create_access_token, create_refresh_token

from app.extensions import db
from app.models import Employee, User

PASSWORD = "Secret123!"  # the password conftest.make_user gives every user
BAD_LOGIN = "Email or password is incorrect."


def sign_in(client, email, password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


# ---------- register ----------


def test_register_creates_an_employee_with_a_hashed_password(client):
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Alex Kamau",
            "email": "Alex@Test.com",
            "password": "Secret123!",
            "role": "admin",
        },
    )

    assert response.status_code == 201
    assert response.json == {"message": "Account created. You can now sign in."}
    user = db.session.scalar(db.select(User).filter_by(email="alex@test.com"))
    assert isinstance(user, Employee)  # the "role": "admin" in the request was ignored
    assert user.password_hash.startswith("$2")  # bcrypt, never the plain password
    assert "Secret123!" not in user.password_hash


def test_register_never_returns_the_password(client):
    response = client.post(
        "/api/auth/register",
        json={"full_name": "Alex Kamau", "email": "alex@test.com", "password": "Secret123!"},
    )

    assert "Secret123!" not in response.get_data(as_text=True)


def test_register_twice_with_the_same_email_is_409(client, make_user):
    make_user("employee", email="taken@test.com")

    response = client.post(
        "/api/auth/register",
        json={"full_name": "Someone", "email": "TAKEN@test.com", "password": "Secret123!"},
    )

    assert response.status_code == 409
    assert response.json["error"]["message"] == "An account with this email already exists."


@pytest.mark.parametrize(
    "body, field",
    [
        ({"full_name": "A", "email": "a@test.com", "password": "Secret123!"}, "full_name"),
        ({"full_name": "Alex", "email": "not-an-email", "password": "Secret123!"}, "email"),
        ({"full_name": "Alex", "email": "a@test.com", "password": "short1"}, "password"),
        ({"full_name": "Alex", "email": "a@test.com", "password": "lettersonly"}, "password"),
        ({"full_name": "Alex", "email": "a@test.com", "password": "12345678"}, "password"),
        ({"full_name": "Alex", "email": "a@test.com", "password": "a1" * 40}, "password"),
        ({"email": "a@test.com", "password": "Secret123!"}, "full_name"),
        ({"full_name": "Alex", "password": "Secret123!"}, "email"),
        ({"full_name": "Alex", "email": "a@test.com"}, "password"),
    ],
)
def test_register_rejects_bad_fields_with_422(client, body, field):
    response = client.post("/api/auth/register", json=body)

    assert response.status_code == 422
    assert field in response.json["error"]["details"]


# ---------- login ----------


def test_login_returns_tokens_that_work(client, make_user):
    make_user("inventory", email="brian@test.com")

    response = sign_in(client, "brian@test.com")

    assert response.status_code == 200
    assert response.json["user"]["role"] == "inventory"
    assert "password" not in response.json["user"]
    assert "password_hash" not in response.json["user"]
    headers = {"Authorization": f"Bearer {response.json['access_token']}"}
    assert client.get("/api/auth/me", headers=headers).json["email"] == "brian@test.com"


def test_login_ignores_email_capitals(client, make_user):
    make_user("employee", email="alex@test.com")

    assert sign_in(client, "ALEX@Test.com").status_code == 200


def test_wrong_password_and_unknown_email_get_the_same_401(client, make_user):
    make_user("employee", email="alex@test.com")

    wrong_password = sign_in(client, "alex@test.com", "Wrong123!")
    unknown_email = sign_in(client, "ghost@test.com", "Wrong123!")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json == unknown_email.json
    assert wrong_password.json["error"]["message"] == BAD_LOGIN
    assert "access_token" not in wrong_password.json


@pytest.mark.parametrize(
    "body",
    [{}, {"email": "alex@test.com"}, {"password": PASSWORD}, {"email": "x", "password": "y"}],
)
def test_login_with_missing_or_bad_fields_is_422(client, body):
    assert client.post("/api/auth/login", json=body).status_code == 422


def test_the_token_carries_the_role(client, make_user, app):
    from flask_jwt_extended import decode_token

    make_user("procurement", email="pm@test.com")

    token = sign_in(client, "pm@test.com").json["access_token"]

    assert decode_token(token)["role"] == "procurement"


# ---------- tokens ----------


def test_refresh_token_gives_a_new_access_token(client, make_user):
    user = make_user("sales")
    refresh = create_refresh_token(identity=user)

    response = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {refresh}"})

    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json['access_token']}"}
    assert client.get("/api/auth/me", headers=headers).status_code == 200


def test_access_token_cannot_be_used_to_refresh(client, make_user):
    access = create_access_token(identity=make_user("sales"))

    response = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {access}"})

    assert response.status_code == 401


def test_refresh_token_cannot_be_used_as_an_access_token(client, make_user):
    refresh = create_refresh_token(identity=make_user("sales"))

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {refresh}"})

    assert response.status_code == 401


def test_expired_token_is_401(client, make_user):
    token = create_access_token(identity=make_user("sales"), expires_delta=timedelta(seconds=-1))

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json["error"]["message"] == "Your session has expired. Please sign in again."


def test_token_of_a_deleted_user_is_401(client, make_user):
    user = make_user("sales")
    token = create_access_token(identity=user)
    db.session.delete(user)
    db.session.commit()

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_refresh_without_any_token_is_401(client):
    assert client.post("/api/auth/refresh").status_code == 401


# ---------- the whole journey ----------


def test_full_signup_and_signin_journey(client):
    """Milestone Gate 3: registration and login work end to end."""
    registered = client.post(
        "/api/auth/register",
        json={"full_name": "Alex Kamau", "email": "alex@test.com", "password": "Secret123!"},
    )
    assert registered.status_code == 201

    response = sign_in(client, "alex@test.com", "Secret123!")

    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json['access_token']}"}
    assert client.get("/api/auth/me", headers=headers).json["role"] == "employee"
    assert client.get("/api/products/", headers=headers).status_code == 200
    assert client.get("/api/auth/me").status_code == 401