import logging

from flask import current_app

log = logging.getLogger(__name__)
outbox = []  # tests read the emails that would have been sent from here


def send_email(to: str, subject: str, text: str) -> None:
    api_key = current_app.config["SENDGRID_API_KEY"]
    if not api_key:
        outbox.append({"to": to, "subject": subject, "text": text})
        log.warning("Email not sent (no SENDGRID_API_KEY). To: %s | %s\n%s", to, subject, text)
        return

    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    message = Mail(
        from_email=current_app.config["MAIL_FROM"],
        to_emails=to,
        subject=subject,
        plain_text_content=text,
    )
    try:
        SendGridAPIClient(api_key).send(message)
    except Exception:
        log.exception("SendGrid could not send the email to %s", to)
        raise