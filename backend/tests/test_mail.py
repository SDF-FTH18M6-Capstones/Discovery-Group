import json

from app.extensions import db
from app.mail import _brevo_send, _smtp_send, build_message, queue_email


class FakeSMTP:
    sent = []

    def __init__(self, host, port, timeout):
        self.host = host

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        self.user = user

    def send_message(self, message):
        FakeSMTP.sent.append(message)


def test_emails_wait_for_the_commit_and_are_dropped_on_rollback(app, outbox):
    queue_email("a@test.com", "Kept", "Body")
    db.session.commit()
    db.session.execute(db.text("SELECT 1"))
    queue_email("b@test.com", "Dropped", "Body")
    db.session.rollback()
    db.session.commit()

    assert [e["subject"] for e in outbox] == ["Kept"]


def test_smtp_sending(app, monkeypatch):
    monkeypatch.setattr("app.mail.smtplib.SMTP", FakeSMTP)
    config = {**app.config, "MAIL_SERVER": "smtp.test", "MAIL_USERNAME": "me", "MAIL_PASSWORD": "x"}
    message = build_message(app, "to@test.com", "Hello", "Body")

    _smtp_send(config, message)

    assert FakeSMTP.sent[-1]["To"] == "to@test.com"


def test_an_smtp_failure_is_logged_not_raised(app, monkeypatch, caplog):
    def broken(*args, **kwargs):
        raise OSError("mail server down")

    monkeypatch.setattr("app.mail.smtplib.SMTP", broken)

    _smtp_send(
        {**app.config, "MAIL_SERVER": "smtp.test"}, build_message(app, "x@test.com", "S", "B")
    )

    assert "Could not send email" in caplog.text


def test_with_a_mail_server_the_send_runs_in_the_background(app, monkeypatch):
    started = []
    monkeypatch.setattr(
        "app.mail.threading.Thread",
        lambda target, args, daemon: type("T", (), {"start": lambda self: started.append(args)})(),
    )
    app.config["MAIL_SERVER"] = "smtp.test"
    try:
        queue_email("a@test.com", "Hi", "Body")
        db.session.commit()
    finally:
        app.config["MAIL_SERVER"] = ""

    assert started[0][1]["Subject"] == "Hi"


def test_brevo_is_used_when_its_key_is_set(app, monkeypatch):
    sent = []

    class Answer:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(request, timeout):
        sent.append(request)
        return Answer()

    monkeypatch.setattr("app.mail.urllib.request.urlopen", fake_urlopen)
    config = {**app.config, "BREVO_API_KEY": "key-123", "MAIL_FROM": "Shop <shop@test.com>"}

    _brevo_send(config, "to@test.com", "Hello", "Body")

    body = json.loads(sent[0].data)
    assert sent[0].full_url == "https://api.brevo.com/v3/smtp/email"
    assert sent[0].headers["Api-key"] == "key-123"
    assert body == {
        "sender": {"name": "Shop", "email": "shop@test.com"},
        "to": [{"email": "to@test.com"}],
        "subject": "Hello",
        "textContent": "Body",
    }


def test_a_brevo_failure_is_logged_not_raised(app, monkeypatch, caplog):
    def broken(*args, **kwargs):
        raise OSError("network down")

    monkeypatch.setattr("app.mail.urllib.request.urlopen", broken)

    _brevo_send({**app.config, "BREVO_API_KEY": "k"}, "x@test.com", "S", "B")

    assert "through Brevo" in caplog.text


def test_unsent_mail_is_printed_when_no_mail_service_is_set_up(app, capsys):
    import logging

    from app.mail import log, print_unsent_mail, send_now

    app.testing = False
    try:
        print_unsent_mail(app)
        send_now(app, "admin@stockpilot.test", "Your sign-in code", "Your code is 482913.")
    finally:
        app.testing = True
        log.handlers.clear()
        log.setLevel(logging.NOTSET)
    assert "482913" in capsys.readouterr().err
