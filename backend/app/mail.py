import json
import logging
import smtplib
import threading
import urllib.request
from email.message import EmailMessage
from email.utils import parseaddr

from flask import current_app, has_app_context
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.extensions import db

log = logging.getLogger("stockpilot.mail")


def queue_email(to, subject, body):
    if not to:
        return
    db.session.info.setdefault("emails", []).append((to, subject, body))


@event.listens_for(Session, "after_commit")
def _send_queued(session):
    emails = session.info.pop("emails", [])
    if not emails or not has_app_context():
        return
    app = current_app._get_current_object()
    for to, subject, body in emails:
        send_now(app, to, subject, body)


@event.listens_for(Session, "after_soft_rollback")
def _drop_queued(session, _previous_transaction):
    session.info.pop("emails", None)


def build_message(app, to, subject, body):
    message = EmailMessage()
    message["From"] = app.config["MAIL_FROM"]
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    return message


BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def send_now(app, to, subject, body):
    config = app.config
    if config.get("BREVO_API_KEY"):
        target, args = _brevo_send, (config.copy(), to, subject, body)
    elif config.get("MAIL_SERVER"):
        target, args = _smtp_send, (config.copy(), build_message(app, to, subject, body))
    else:
        app.extensions.setdefault("outbox", []).append({"to": to, "subject": subject, "body": body})
        log.info("Email to %s: %s\n%s", to, subject, body)
        return
    threading.Thread(target=target, args=args, daemon=True).start()


def brevo_payload(config, to, subject, body):
    name, address = parseaddr(config["MAIL_FROM"])
    return {
        "sender": {"name": name or "StockPilot", "email": address},
        "to": [{"email": to}],
        "subject": subject,
        "textContent": body,
    }


def _brevo_send(config, to, subject, body):
    request = urllib.request.Request(
        BREVO_URL,
        data=json.dumps(brevo_payload(config, to, subject, body)).encode(),
        headers={
            "api-key": config["BREVO_API_KEY"],
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response.read()
    except Exception:  # an email failing must never break the app
        log.exception("Could not send email to %s through Brevo", to)


def _smtp_send(config, message):
    try:
        with smtplib.SMTP(config["MAIL_SERVER"], config["MAIL_PORT"], timeout=15) as smtp:
            if config.get("MAIL_USE_TLS"):
                smtp.starttls()
            if config.get("MAIL_USERNAME"):
                smtp.login(config["MAIL_USERNAME"], config["MAIL_PASSWORD"])
            smtp.send_message(message)
    except Exception:  # an email failing must never break the app
        log.exception("Could not send email to %s", message["To"])
