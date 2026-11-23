from flask import current_app

from app.extensions import db
from app.mail import queue_email
from app.models import Notification, User


def notify(user_ids, message, link=None, email_subject=None):
    ids = {uid for uid in user_ids if uid}
    for user_id in ids:
        db.session.add(Notification(user_id=user_id, message=message, link=link))
    if email_subject and ids:
        users = db.session.scalars(
            db.select(User).where(User.id.in_(ids), User.is_active.is_(True))
        ).all()
        for user in users:
            queue_email(user.email, email_subject, email_body(user, message, link))


def notify_roles(roles, message, exclude=None, link=None, email_subject=None):
    ids = db.session.scalars(
        db.select(User.id).where(User.role.in_(roles), User.is_active.is_(True))
    ).all()
    notify([uid for uid in ids if uid != exclude], message, link, email_subject)


def email_body(user, message, link):
    lines = [f"Hello {user.full_name},", "", message]
    if link:
        lines += ["", f"Open it in StockPilot: {current_app.config['FRONTEND_URL']}{link}"]
    lines += ["", "— StockPilot"]
    return "\n".join(lines)


def warn_if_low(product, before, actor_id=None):
    after = product.quantity
    level = product.reorder_level
    crossed_reorder = before > level >= after
    ran_out = before > 0 and after == 0
    if not (crossed_reorder or ran_out):
        return
    left = "is out of stock" if after == 0 else f"is low on stock ({after} left)"
    notify_roles(
        ("admin", "inventory"),
        f"{product.name} {left}.",
        exclude=actor_id,
        link=f"/products/{product.id}",
        email_subject=f"Low stock: {product.name}",
    )
