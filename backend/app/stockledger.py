from app.extensions import db
from app.models import StockMovement


def move_stock(product, change, type_, user_id, reference=None, reason=None):
    product.quantity += change
    movement = StockMovement(
        product=product,
        change=change,
        quantity_after=product.quantity,
        type=type_,
        reference=reference,
        reason=reason,
        user_id=user_id,
    )
    db.session.add(movement)
    return movement
