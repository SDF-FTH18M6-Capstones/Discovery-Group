from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Admin, ProcurementManager, Product, User


def test_roles_load_as_their_own_class(app):
    db.session.add(ProcurementManager(full_name="Carlos", email="carlos@test.com", password_hash="x"))
    db.session.commit()
    db.session.expire_all()

    user = db.session.scalar(db.select(User).filter_by(email="carlos@test.com"))

    assert isinstance(user, ProcurementManager)
    assert user.can_approve_requests is True
    assert Admin.can_approve_requests is False


def test_stock_can_never_go_negative(app, category):
    product = Product(
        sku="SP-9",
        name="Tea",
        category=category,
        cost_price=Decimal("1"),
        selling_price=Decimal("2"),
        quantity=-1,
    )
    db.session.add(product)

    with pytest.raises(IntegrityError):
        db.session.commit()


def test_password_saved_in_an_old_format_is_refused_not_crashed(app, employee):
    employee.password_hash = "pbkdf2:sha256:600000$abc$def"
    db.session.commit()

    assert employee.check_password("Secret123!") is False