from flask_jwt_extended import current_user

from app.extensions import db
from app.models import AuditLog


def actor_id():
    try:
        return current_user.id if current_user else None
    except RuntimeError:
        return None


SIGNED_IN_USER = object()


def audit(action, entity_type, entity_id, summary, changes=None, user_id=SIGNED_IN_USER):
    entry = AuditLog(
        user_id=actor_id() if user_id is SIGNED_IN_USER else user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        changes=changes or None,
    )
    db.session.add(entry)
    return entry


def diff(item, data, fields=None):
    changes = {}
    for key, new in data.items():
        if fields is not None and key not in fields:
            continue
        old = getattr(item, key, None)
        if old != new:
            changes[key] = [jsonable(old), jsonable(new)]
    return changes


def jsonable(value):
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return str(value)
