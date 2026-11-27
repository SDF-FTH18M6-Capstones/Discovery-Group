import json
import logging
import re
import threading
import urllib.error
import urllib.request

from flask import current_app, has_app_context
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.extensions import db

log = logging.getLogger("stockpilot.whatsapp")


def normalise(number):
    digits = re.sub(r"\D", "", number or "")
    if digits.startswith("0"):
        digits = "254" + digits[1:]
    elif len(digits) == 9 and digits[0] in "17":
        digits = "254" + digits
    return digits if 10 <= len(digits) <= 15 else None


def tidy(text, limit=900):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def queue_alert(business, message):
    if business is None or not business.whatsapp_alerts or not business.whatsapp_number:
        return False
    db.session.info.setdefault("whatsapp", []).append(
        (business.whatsapp_number, tidy(business.name, 60), tidy(message))
    )
    return True


@event.listens_for(Session, "after_commit")
def _send_queued(session):
    queued = session.info.pop("whatsapp", [])
    if not queued or not has_app_context():
        return
    app = current_app._get_current_object()
    for number, name, message in queued:
        send_now(app, number, name, message)


@event.listens_for(Session, "after_rollback")
def _forget_queued(session):
    session.info.pop("whatsapp", None)


def payload(config, number, name, message):
    return {
        "messaging_product": "whatsapp",
        "to": number,
        "type": "template",
        "template": {
            "name": config["WHATSAPP_TEMPLATE"],
            "language": {"code": config["WHATSAPP_LANGUAGE"]},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": name},
                        {"type": "text", "text": message},
                    ],
                }
            ],
        },
    }


def send_now(app, number, name, message):
    config = app.config
    if not (config.get("WHATSAPP_TOKEN") and config.get("WHATSAPP_PHONE_ID")):
        app.extensions.setdefault("whatsapp_outbox", []).append(
            {"to": number, "business": name, "message": message}
        )
        log.info("WhatsApp to %s: %s", number, message)
        return
    body = payload(config, number, name, message)
    threading.Thread(target=deliver, args=(config.copy(), body), daemon=True).start()


def deliver(config, body):
    request = urllib.request.Request(
        f"https://graph.facebook.com/{config['WHATSAPP_API_VERSION']}/"
        f"{config['WHATSAPP_PHONE_ID']}/messages",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {config['WHATSAPP_TOKEN']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status < 300
    except (urllib.error.URLError, TimeoutError) as err:
        log.warning("Could not send a WhatsApp alert to %s: %s", body["to"], err)
        return False
