from flask import current_app

from app.extensions import db
from app.mail import queue_email
from app.models import Notification, User
from app.shoptime import current_business
from app.whatsapp import queue_alert


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


def staff_ids(roles):
    return db.session.scalars(
        db.select(User.id).where(
            User.role.in_(roles), User.is_active.is_(True), User.approved_at.is_not(None)
        )
    ).all()


def notify_roles(roles, message, exclude=None, link=None, email_subject=None):
    ids = staff_ids(roles)
    if not ids and "admin" not in roles:
        ids = staff_ids(("admin",))
    notify([uid for uid in ids if uid != exclude], message, link, email_subject)


def email_body(user, message, link):
    lines = [f"Hello {user.full_name},", "", message]
    if link:
        lines += ["", f"Open it in StockPilot: {current_app.config['FRONTEND_URL']}{link}"]
    lines += ["", "— StockPilot"]
    return "\n".join(lines)


def on_order(purchase):
    if purchase.status == "ordered":
        return f"{purchase.reference} was sent to the supplier automatically."
    return f"It was added to {purchase.reference}, ready to confirm."


def order_if_low(product, actor_id):
    from app.reorder import draft_for_low_stock

    if not product.is_active or product.quantity > product.reorder_level:
        return None
    draft = draft_for_low_stock(product, actor_id)
    if draft is not None:
        notify_roles(
            ("procurement",),
            f"{product.name} is low on stock ({product.quantity} left). {on_order(draft)}",
            exclude=actor_id,
            link=f"/purchases?open={draft.id}",
        )
    return draft


def warn_if_low(product, before, actor_id):
    from app.reorder import draft_for_low_stock

    after = product.quantity
    level = product.reorder_level
    crossed_reorder = before > level >= after
    ran_out = before > 0 and after == 0
    if not (crossed_reorder or ran_out):
        return
    left = "is out of stock" if after == 0 else f"is low on stock ({after} left)"
    draft = draft_for_low_stock(product, actor_id)
    if draft is not None:
        message = f"{product.name} {left}. {on_order(draft)}"
        link = f"/purchases?open={draft.id}"
    else:
        message = f"{product.name} {left}."
        link = f"/products/{product.id}"
    notify_roles(
        ("inventory", "procurement"),
        message,
        exclude=actor_id,
        link=link,
        email_subject=f"Low stock: {product.name}",
    )
    queue_alert(current_business(), message)
