import pytest
from flask_jwt_extended import create_access_token
from sqlalchemy import text

from app import create_app
from app.config import TestConfig
from app.extensions import db as _db

PASSWORD = "Secret123!"


@pytest.fixture(scope="session")
def _schema():
    app = create_app(TestConfig)
    with app.app_context():
        _db.drop_all()
        _db.create_all()
    yield
    with app.app_context():
        _db.drop_all()


@pytest.fixture()
def app(_schema):
    app = create_app(TestConfig)
    with app.app_context():
        yield app
        _db.session.remove()
        tables = ", ".join(t.name for t in _db.metadata.sorted_tables)
        _db.session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        _db.session.commit()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def make_user(app):
    from app.models import ROLE_CLASSES

    counter = {"n": 0}

    def make(role="employee", email=None, password=PASSWORD, full_name=None):
        counter["n"] += 1
        user = ROLE_CLASSES[role](
            full_name=full_name or f"{role.title()} User {counter['n']}",
            email=email or f"{role}{counter['n']}@test.com",
        )
        user.set_password(password)
        _db.session.add(user)
        _db.session.commit()
        return user

    return make


class AuthClient:
   

    def __init__(self, client, user):
        self.client = client
        self.user = user
        self.headers = {"Authorization": f"Bearer {create_access_token(identity=user)}"}

    def open(self, method, url, **kwargs):
        return self.client.open(url, method=method, headers=self.headers, **kwargs)

    def get(self, url, **kwargs):
        return self.open("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.open("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self.open("PUT", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.open("DELETE", url, **kwargs)


@pytest.fixture()
def as_role(client, make_user):
    def login_as(role):
        return AuthClient(client, make_user(role))

    return login_as


@pytest.fixture()
def admin(as_role):
    return as_role("admin")


@pytest.fixture()
def category(app):
    from app.models import Category

    item = Category(name="Beverages")
    _db.session.add(item)
    _db.session.commit()
    return item


@pytest.fixture()
def employee(make_user):
    return make_user("employee", email="barclay@test.com", full_name="Barclay Koin")