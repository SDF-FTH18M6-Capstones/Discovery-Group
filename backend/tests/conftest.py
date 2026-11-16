import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db as _db


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        _db.drop_all()
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def category(app):
    from app.models import Category

    item = Category(name="Beverages")
    _db.session.add(item)
    _db.session.commit()
    return item


@pytest.fixture()
def employee(app):
    from app.models import Employee

    user = Employee(full_name="Alex Kamau", email="alex@test.com")
    user.set_password("Secret123!")
    _db.session.add(user)
    _db.session.commit()
    return user