import logging
import smtplib
from email.message import EmailMessage

from flask import current_app

log = logging.getLogger(__name__)
outbox = []  # tests read the emails that would have been sent from here


def send_email(to: str, subject: str, text: str) -> None:
    config = current_app.config
    if config["SMTP_HOST"]:
        _send_smtp(config, to, subject, text)
    elif config["SENDGRID_API_KEY"]:
        _send_sendgrid(config, to, subject, text)
    else:
        outbox.append({"to": to, "subject": subject, "text": text})
        log.warning("Email not sent (no email service set up). To: %s | %s\n%s", to, subject, text)


def _send_smtp(config, to, subject, text):
    message = EmailMessage()
    message["From"] = config["MAIL_FROM"]
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    try:
        with smtplib.SMTP(config["SMTP_HOST"], config["SMTP_PORT"], timeout=15) as server:
            server.starttls()
            server.login(config["SMTP_USERNAME"], config["SMTP_PASSWORD"])
            server.send_message(message)
    except (smtplib.SMTPException, OSError):
        log.exception("Could not send the email to %s through %s", to, config["SMTP_HOST"])
        raise


def _send_sendgrid(config, to, subject, text):
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    message = Mail(
        from_email=config["MAIL_FROM"], to_emails=to, subject=subject, plain_text_content=text
    )
    try:
        SendGridAPIClient(config["SENDGRID_API_KEY"]).send(message)
    except Exception:
        log.exception("SendGrid could not send the email to %s", to)
        raise