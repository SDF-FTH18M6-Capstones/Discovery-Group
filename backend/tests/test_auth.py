import re
from datetime import UTC, datetime, timedelta

import pytest
from flask_jwt_extended import create_access_token, create_refresh_token

from app.email import outbox
from app.extensions import db
from app.models import Employee, User

PASSWORD = "Secret123!"  # the password conftest.make_user gives every user
BAD_LOGIN = "Email or password is incorrect."
BAD_CODE = "The code is wrong or has expired. Sign in again to get a new code."


def last_email():
    return outbox[-1]


def token_from_email():
    return re.search(r"token=(\S+)", last_email()["text"]).group(1)


def code_from_email():
    return re.search(r"\b(\d{6})\b", last_email()["text"]).group(1)


def sign_in(client, email, password=PASSWORD):
    assert (
        client.post("/api/auth/login", json={"email": email, "password": password}).status_code
        == 200
    )
    return client.post("/api/auth/verify-otp", json={"email": email, "code": code_from_email()})


# ---------- register ----------


def test_register_creates_an_unverified_employee_and_emails_a_link(client):
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
    user = db.session.scalar(db.select(User).filter_by(email="alex@test.com"))
    assert isinstance(user, Employee)  # the "role": "admin" in the request was ignored
    assert user.is_verified is False
    assert user.password_hash.startswith("$2")  # bcrypt, never the plain password
    assert last_email()["to"] == "alex@test.com"
    assert "verify-email?token=" in last_email()["text"]


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


# ---------- verify email ----------


def test_verification_link_activates_the_account(client):
    client.post(
        "/api/auth/register",
        json={"full_name": "Alex", "email": "alex@test.com", "password": "Secret123!"},
    )

    response = client.post("/api/auth/verify-email", json={"token": token_from_email()})

    assert response.status_code == 200
    assert db.session.scalar(db.select(User).filter_by(email="alex@test.com")).is_verified


def test_tampered_link_is_400(client):
    response = client.post("/api/auth/verify-email", json={"token": "made-up-token"})

    assert response.status_code == 400
    assert response.json["error"]["message"] == "This link is not valid."


def test_expired_link_is_400(client, monkeypatch):
    client.post(
        "/api/auth/register",
        json={"full_name": "Alex", "email": "alex@test.com", "password": "Secret123!"},
    )
    token = token_from_email()
    later = datetime.now(UTC) + timedelta(hours=25)
    monkeypatch.setattr("itsdangerous.timed.time.time", lambda: later.timestamp())

    response = client.post("/api/auth/verify-email", json={"token": token})

    assert response.status_code == 400
    assert "expired" in response.json["error"]["message"]


def test_resend_verification_never_reveals_whether_an_email_exists(client, make_user):
    make_user("employee", email="new@test.com", verified=False)

    unknown = client.post("/api/auth/resend-verification", json={"email": "nobody@test.com"})
    known = client.post("/api/auth/resend-verification", json={"email": "new@test.com"})

    assert unknown.status_code == known.status_code == 200
    assert unknown.json == known.json
    assert [e["to"] for e in outbox] == ["new@test.com"]


# ---------- login step 1 ----------


def test_wrong_password_and_unknown_email_get_the_same_401(client, make_user):
    make_user("employee", email="alex@test.com")

    wrong_password = client.post(
        "/api/auth/login", json={"email": "alex@test.com", "password": "Wrong123!"}
    )
    unknown_email = client.post(
        "/api/auth/login", json={"email": "ghost@test.com", "password": "Wrong123!"}
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json == unknown_email.json
    assert wrong_password.json["error"]["message"] == BAD_LOGIN


def test_unverified_account_cannot_sign_in(client, make_user):
    make_user("employee", email="alex@test.com", verified=False)

    response = client.post("/api/auth/login", json={"email": "alex@test.com", "password": PASSWORD})

    assert response.status_code == 403
    assert outbox == []


def test_login_emails_a_code_and_stores_only_its_hash(client, make_user):
    user = make_user("employee", email="alex@test.com")

    response = client.post("/api/auth/login", json={"email": "alex@test.com", "password": PASSWORD})

    assert response.status_code == 200
    assert "dev_code" not in response.json
    code = code_from_email()
    db.session.refresh(user)
    assert user.otp_hash and code not in user.otp_hash


@pytest.mark.parametrize(
    "body",
    [{}, {"email": "alex@test.com"}, {"password": PASSWORD}, {"email": "x", "password": "y"}],
)
def test_login_with_missing_or_bad_fields_is_422(client, body):
    assert client.post("/api/auth/login", json=body).status_code == 422


# ---------- login step 2 ----------


def test_correct_code_returns_tokens_that_work(client, make_user):
    make_user("inventory", email="brian@test.com")

    response = sign_in(client, "brian@test.com")

    assert response.status_code == 200
    assert response.json["user"]["role"] == "inventory"
    headers = {"Authorization": f"Bearer {response.json['access_token']}"}
    assert client.get("/api/auth/me", headers=headers).json["email"] == "brian@test.com"


def test_a_code_works_only_once(client, make_user):
    make_user("employee", email="alex@test.com")
    client.post("/api/auth/login", json={"email": "alex@test.com", "password": PASSWORD})
    code = code_from_email()

    first = client.post("/api/auth/verify-otp", json={"email": "alex@test.com", "code": code})
    second = client.post("/api/auth/verify-otp", json={"email": "alex@test.com", "code": code})

    assert first.status_code == 200
    assert second.status_code == 401


def test_wrong_code_is_401(client, make_user):
    make_user("employee", email="alex@test.com")
    client.post("/api/auth/login", json={"email": "alex@test.com", "password": PASSWORD})
    wrong = "000000" if code_from_email() != "000000" else "111111"

    response = client.post("/api/auth/verify-otp", json={"email": "alex@test.com", "code": wrong})

    assert response.status_code == 401
    assert response.json["error"]["message"] == BAD_CODE


def test_five_wrong_codes_lock_the_code_even_if_the_sixth_is_right(client, make_user):
    make_user("employee", email="alex@test.com")
    client.post("/api/auth/login", json={"email": "alex@test.com", "password": PASSWORD})
    code = code_from_email()
    wrong = "000000" if code != "000000" else "111111"

    for _ in range(5):
        client.post("/api/auth/verify-otp", json={"email": "alex@test.com", "code": wrong})
    response = client.post("/api/auth/verify-otp", json={"email": "alex@test.com", "code": code})

    assert response.status_code == 401


def test_expired_code_is_401(client, make_user):
    user = make_user("employee", email="alex@test.com")
    client.post("/api/auth/login", json={"email": "alex@test.com", "password": PASSWORD})
    code = code_from_email()
    user.otp_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.session.commit()

    response = client.post("/api/auth/verify-otp", json={"email": "alex@test.com", "code": code})

    assert response.status_code == 401


def test_code_without_a_login_first_is_401(client, make_user):
    make_user("employee", email="alex@test.com")

    response = client.post(
        "/api/auth/verify-otp", json={"email": "alex@test.com", "code": "123456"}
    )

    assert response.status_code == 401


@pytest.mark.parametrize("code", ["12345", "1234567", "12ab56", ""])
def test_code_must_be_six_digits(client, code):
    response = client.post("/api/auth/verify-otp", json={"email": "alex@test.com", "code": code})

    assert response.status_code == 422
    assert "code" in response.json["error"]["details"]


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
    client.post(
        "/api/auth/register",
        json={"full_name": "Alex Kamau", "email": "alex@test.com", "password": "Secret123!"},
    )
    client.post("/api/auth/verify-email", json={"token": token_from_email()})

    response = sign_in(client, "alex@test.com", "Secret123!")

    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json['access_token']}"}
    assert client.get("/api/auth/me", headers=headers).json["role"] == "employee"
    assert client.get("/api/products/", headers=headers).status_code == 200
    assert client.get("/api/auth/me").status_code == 401