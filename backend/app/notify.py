from app.extensions import db
from app.models import Notification, User


def notify(user_ids, message):
    for user_id in {uid for uid in user_ids if uid}:
        db.session.add(Notification(user_id=user_id, message=message))


def notify_roles(roles, message, exclude=None):
    ids = db.session.scalars(db.select(User.id).where(User.role.in_(roles))).all()
    notify([uid for uid in ids if uid != exclude], message)


def warn_if_low(product, actor_id=None):
    """Tell Admin and Inventory when a product reaches its reorder level."""
    if product.quantity <= product.reorder_level:
        if product.quantity == 0:
            left = "is out of stock"
        else:
            left = f"is low on stock ({product.quantity} left)"
        notify_roles(("admin", "inventory"), f"{product.name} {left}.", exclude=actor_id)
