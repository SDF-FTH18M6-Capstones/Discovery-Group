import logging
import smtplib
import threading
from email.message import EmailMessage

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


def send_now(app, to, subject, body):
    if not app.config.get("MAIL_SERVER"):
        app.extensions.setdefault("outbox", []).append({"to": to, "subject": subject, "body": body})
        log.info("Email to %s: %s\n%s", to, subject, body)
        return
    message = build_message(app, to, subject, body)
    thread = threading.Thread(target=_smtp_send, args=(app.config.copy(), message), daemon=True)
    thread.start()


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
