"""Which email service is used, decided by the settings. Nothing is really sent."""

import smtplib

import pytest

from app.email import outbox, send_email


class FakeSMTP:
    """Stands in for smtplib.SMTP and records what would have been sent."""

    sent = []

    def __init__(self, host, port, timeout):
        self.host, self.port = host, port
        self.steps = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.steps.append("starttls")

    def login(self, username, password):
        if password != "apppassword1234":
            raise smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")
        self.steps.append(("login", username))

    def send_message(self, message):
        FakeSMTP.sent.append((self.host, self.port, self.steps, message))


@pytest.fixture()
def gmail(app, monkeypatch):
    FakeSMTP.sent = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setitem(app.config, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setitem(app.config, "SMTP_USERNAME", "team@gmail.com")
    monkeypatch.setitem(app.config, "SMTP_PASSWORD", "apppassword1234")
    monkeypatch.setitem(app.config, "MAIL_FROM", "team@gmail.com")
    return FakeSMTP


def test_without_an_email_service_the_email_goes_to_the_outbox(app):
    with app.app_context():
        send_email("a@test.com", "Hello", "Body")

    assert outbox == [{"to": "a@test.com", "subject": "Hello", "text": "Body"}]


def test_gmail_settings_send_over_smtp_with_tls(app, gmail):
    with app.app_context():
        send_email("a@test.com", "Your code", "123456")

    host, port, steps, message = gmail.sent[0]
    assert (host, port) == ("smtp.gmail.com", 587)
    assert steps == ["starttls", ("login", "team@gmail.com")]
    assert message["To"] == "a@test.com"
    assert message["From"] == "team@gmail.com"
    assert message.get_content().strip() == "123456"
    assert outbox == []


def test_a_wrong_app_password_is_reported(app, gmail):
    app.config["SMTP_PASSWORD"] = "wrong"
    with app.app_context(), pytest.raises(smtplib.SMTPAuthenticationError):
        send_email("a@test.com", "Your code", "123456")


def test_registering_with_gmail_set_up_emails_the_link(client, gmail):
    response = client.post(
        "/api/auth/register",
        json={"full_name": "Alex Kamau", "email": "alex@test.com", "password": "Secret123!"},
    )

    assert response.status_code == 201
    message = gmail.sent[0][3]
    assert message["To"] == "alex@test.com"
    assert "/verify-email?token=" in message.get_content()