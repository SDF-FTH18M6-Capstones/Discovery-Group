from decimal import Decimal

import pytest
from sqlalchemy import event

from app.extensions import db
from app.models import Asset, Category, Product, Request


class QueryCounter:
    def __init__(self):
        self.count = 0

    def __call__(self, *args):
        self.count += 1


def count_queries(client, url):
    counter = QueryCounter()
    engine = db.engine
    event.listen(engine, "before_cursor_execute", counter)
    try:
        assert client.get(url).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", counter)
    return counter.count


def add_rows(start, rows, make_user):
    people = [make_user("employee") for _ in range(rows)]
    categories = [Category(name=f"Category {start + i}") for i in range(rows)]
    db.session.add_all(categories)
    db.session.flush()
    for i in range(rows):
        db.session.add(
            Product(
                sku=f"SP-{start + i}",
                name=f"Product {start + i}",
                category_id=categories[i].id,
                cost_price=Decimal("1"),
                selling_price=Decimal("2"),
            )
        )
        db.session.add(Request(requester_id=people[i].id, item="Pens", quantity=1, reason="Pens"))
        db.session.add(
            Asset(
                asset_code=f"AST-{start + i}",
                name="Laptop",
                status="assigned",
                assigned_to=people[i].id,
            )
        )
    db.session.commit()


@pytest.mark.parametrize("url", ["/api/products/", "/api/requests/", "/api/assets/"])
def test_more_rows_do_not_mean_more_queries(admin, make_user, url):
    add_rows(0, 3, make_user)
    few = count_queries(admin, url)
    add_rows(100, 12, make_user)
    many = count_queries(admin, url)

    assert many == few