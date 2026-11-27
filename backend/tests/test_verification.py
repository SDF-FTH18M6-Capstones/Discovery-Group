import re
from datetime import UTC, datetime, timedelta

import pytest

from app.extensions import db
from app.models import EmailVerification, LoginChallenge, User
from tests.conftest import PASSWORD


@pytest.fixture()
def strict(app):
    app.config.update(
        EMAIL_VERIFICATION_REQUIRED=True,
        LOGIN_CODE_REQUIRED=True,
        LOGIN_CODE_EXEMPT_DOMAINS=[],
    )
    yield app
    app.config.update(EMAIL_VERIFICATION_REQUIRED=False, LOGIN_CODE_REQUIRED=False)


def last_link(outbox):
    return re.search(r"verify-email\?token=(\S+)", outbox[-1]["body"]).group(1)


def last_code(outbox):
    return re.search(r"\b(\d{6})\b", outbox[-1]["subject"]).group(1)


def sign_in(client, email, password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def join(client, email="barclay@test.com"):
    return client.post(
        "/api/auth/register",
        json={
            "full_name": "Barclay Koin",
            "email": email,
            "password": PASSWORD,
            "join_code": "TESTJOIN",
        },
    )


def test_a_new_account_must_confirm_its_email_before_signing_in(strict, client, outbox):
    joined = join(client)

    assert joined.status_code == 201
    assert "to confirm your email" in joined.json["message"]
    assert outbox[-1]["subject"] == "Confirm your StockPilot email"
    blocked = sign_in(client, "barclay@test.com")
    assert blocked.status_code == 403
    assert blocked.json["error"]["reason"] == "email_unverified"

    confirmed = client.post("/api/auth/verify-email", json={"token": last_link(outbox)})
    assert confirmed.status_code == 200
    assert db.session.scalar(db.select(User).filter_by(email="barclay@test.com")).email_verified

    again = client.post("/api/auth/verify-email", json={"token": last_link(outbox)})
    assert again.status_code == 400
    assert again.json["error"]["reason"] == "link_invalid"


def test_a_new_business_owner_confirms_before_being_signed_in(strict, client, outbox):
    response = client.post(
        "/api/auth/register-business",
        json={
            "business_name": "Mama Mboga",
            "full_name": "Wanjiku Kamau",
            "email": "w@mboga.test",
            "password": PASSWORD,
        },
    )

    assert response.status_code == 201
    assert response.json["verification_required"] is True
    assert "access_token" not in response.json
    assert outbox[-1]["to"] == "w@mboga.test"


def test_an_expired_link_is_refused_and_a_new_one_can_be_sent(strict, client, outbox):
    join(client)
    row = db.session.scalar(db.select(EmailVerification))
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.session.commit()

    expired = client.post("/api/auth/verify-email", json={"token": last_link(outbox)})
    resent = client.post("/api/auth/resend-verification", json={"email": "barclay@test.com"})
    unknown = client.post("/api/auth/resend-verification", json={"email": "nobody@test.com"})

    assert expired.status_code == 400
    assert resent.json == unknown.json
    assert len(outbox) == 2
    assert (
        client.post("/api/auth/verify-email", json={"token": last_link(outbox)}).status_code == 200
    )


def test_a_correct_password_sends_a_code_and_the_code_signs_in(strict, client, make_user, outbox):
    make_user("sales", email="vincent@test.com")

    step1 = sign_in(client, "vincent@test.com")

    assert step1.status_code == 200
    assert step1.json["code_required"] is True
    assert "access_token" not in step1.json
    assert step1.json["email_hint"] == "v••••••@test.com"
    assert (step1.json["expires_in"], step1.json["resend_after"]) == (300, 60)
    code = last_code(outbox)
    step2 = client.post(
        "/api/auth/login/verify", json={"challenge_id": step1.json["challenge_id"], "code": code}
    )
    assert step2.status_code == 200
    assert step2.json["user"]["email"] == "vincent@test.com"
    headers = {"Authorization": f"Bearer {step2.json['access_token']}"}
    assert client.get("/api/auth/me", headers=headers).status_code == 200

    reused = client.post(
        "/api/auth/login/verify", json={"challenge_id": step1.json["challenge_id"], "code": code}
    )
    assert reused.status_code == 401


def test_five_wrong_codes_cancel_the_sign_in(strict, client, make_user, outbox):
    make_user("sales", email="vincent@test.com")
    challenge = sign_in(client, "vincent@test.com").json["challenge_id"]
    code = last_code(outbox)
    wrong = "000000" if code != "000000" else "111111"

    answers = [
        client.post("/api/auth/login/verify", json={"challenge_id": challenge, "code": wrong})
        for _ in range(5)
    ]

    assert [a.status_code for a in answers] == [401] * 5
    assert answers[0].json["error"]["message"] == "That code is not right. 4 tries left."
    assert answers[3].json["error"]["message"] == "That code is not right. 1 try left."
    assert answers[4].json["error"]["message"].startswith("Too many wrong codes")
    late = client.post("/api/auth/login/verify", json={"challenge_id": challenge, "code": code})
    assert late.status_code == 401


def test_an_expired_code_is_refused(strict, client, make_user, outbox):
    make_user("sales", email="vincent@test.com")
    challenge_id = sign_in(client, "vincent@test.com").json["challenge_id"]
    row = db.session.get(LoginChallenge, challenge_id)
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.session.commit()

    response = client.post(
        "/api/auth/login/verify", json={"challenge_id": challenge_id, "code": last_code(outbox)}
    )

    assert response.status_code == 401
    assert "expired" in response.json["error"]["message"]


def test_a_new_code_only_after_60_seconds_and_the_old_one_stops(strict, client, make_user, outbox):
    make_user("sales", email="vincent@test.com")
    challenge_id = sign_in(client, "vincent@test.com").json["challenge_id"]
    first = last_code(outbox)

    too_soon = client.post("/api/auth/login/resend", json={"challenge_id": challenge_id})
    assert too_soon.status_code == 429
    assert too_soon.json["error"]["message"].startswith("Wait ")

    row = db.session.get(LoginChallenge, challenge_id)
    row.sent_at = datetime.now(UTC) - timedelta(seconds=61)
    db.session.commit()
    resent = client.post("/api/auth/login/resend", json={"challenge_id": challenge_id})
    second = last_code(outbox)

    assert resent.status_code == 200
    assert len(outbox) == 2
    if first != second:
        old = client.post(
            "/api/auth/login/verify", json={"challenge_id": challenge_id, "code": first}
        )
        assert old.status_code == 401
    ok = client.post("/api/auth/login/verify", json={"challenge_id": challenge_id, "code": second})
    assert ok.status_code == 200


def test_wrong_passwords_still_give_one_message_and_no_code(strict, client, make_user, outbox):
    make_user("sales", email="vincent@test.com")

    wrong = sign_in(client, "vincent@test.com", "Wrong123!")
    unknown = sign_in(client, "nobody@test.com", "Wrong123!")

    assert wrong.json == unknown.json
    assert outbox == []


def test_demo_domains_can_skip_the_code(strict, client, make_user):
    strict.config["LOGIN_CODE_EXEMPT_DOMAINS"] = ["stockpilot.test"]
    make_user("admin", email="admin@stockpilot.test")

    response = sign_in(client, "admin@stockpilot.test")

    assert "access_token" in response.json


def test_a_password_reset_also_confirms_the_email(strict, client, make_user, outbox):
    make_user("employee", email="barclay@test.com", verified=False)
    client.post("/api/auth/forgot-password", json={"email": "barclay@test.com"})
    token = re.search(r"token=(\S+)", outbox[-1]["body"]).group(1)

    client.post("/api/auth/reset-password", json={"token": token, "password": "Brand9New"})

    assert db.session.scalar(db.select(User).filter_by(email="barclay@test.com")).email_verified
