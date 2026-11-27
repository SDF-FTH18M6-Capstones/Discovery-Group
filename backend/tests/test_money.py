import io
from datetime import UTC, datetime
from decimal import Decimal

from app.extensions import db
from app.models import Category, CategoryRule, MoneyTransaction, Product, Sale, Supplier
from tests.statement_files import statement_pdf

ROWS = [
    "TAQ1AAAAAA 2026-11-02 08:00:00 Funds received from - 0712***678 MARY W COMPLETED"
    " 300.00 0.00 1,300.00",
    "TAQ1AAAAAB 2026-11-02 09:00:00 Pay Bill Online to 888880 - KPLC PREPAID COMPLETED"
    " 0.00 450.00 850.00",
    "TAQ1AAAAAC 2026-11-02 10:00:00 Merchant Payment to 5544 - METRO WHOLESALE COMPLETED"
    " 0.00 600.00 250.00",
    "TAQ1AAAAAD 2026-11-02 10:00:01 Customer Transfer of Funds Charge COMPLETED 0.00 7.00 243.00",
    "TAQ1AAAAAE 2026-11-02 11:00:00 Customer Transfer to - 0700***111 BOB COMPLETED"
    " 0.00 100.00 143.00",
]


def upload(client, data, password="4321", name="statement.pdf"):
    return client.post(
        "/api/money/statement",
        data={"file": (io.BytesIO(data), name), "password": password},
        content_type="multipart/form-data",
    )


def by_receipt():
    return {t.receipt: t for t in db.session.scalars(db.select(MoneyTransaction))}


def test_a_statement_is_imported_and_sorted_into_categories(admin):
    db.session.add(Supplier(name="Metro Wholesale"))
    db.session.commit()

    response = upload(admin, statement_pdf(ROWS))

    assert response.status_code == 201
    assert (response.json["added"], response.json["duplicates"], response.json["source"]) == (
        5,
        0,
        "statement",
    )
    rows = by_receipt()
    assert {receipt: row.category for receipt, row in rows.items()} == {
        "TAQ1AAAAAA": "sales",
        "TAQ1AAAAAB": "utilities",
        "TAQ1AAAAAC": "stock",
        "TAQ1AAAAAD": "fees",
        "TAQ1AAAAAE": "other_expense",
    }
    assert rows["TAQ1AAAAAA"].occurred_at == datetime(2026, 11, 2, 5, 0, tzinfo=UTC)


def test_the_same_statement_twice_adds_nothing(admin):
    upload(admin, statement_pdf(ROWS))

    again = upload(admin, statement_pdf(ROWS)).json

    assert (again["added"], again["duplicates"]) == (0, 5)


def test_wrong_passwords_and_odd_files_are_explained(admin):
    wrong = upload(admin, statement_pdf(ROWS), password="0000")
    odd = upload(admin, b"hello", name="notes.txt")
    empty = upload(admin, statement_pdf(["nothing useful here"]))

    assert (wrong.status_code, wrong.json["error"]["message"]) == (
        422,
        "That password did not open the statement.",
    )
    assert odd.status_code == 400
    assert empty.status_code == 422
    assert "No completed M-Pesa transactions" in empty.json["error"]["message"]


def test_a_file_must_be_chosen(admin):
    assert admin.post("/api/money/statement", data={}).status_code == 400


def test_csv_statements_work_too(admin):
    data = (
        b"Receipt No,Completion Time,Details,Transaction Status,Paid In,Withdrawn,Balance\n"
        b"TAQ1AAAAAA,2026-11-02 08:00:00,Funds received from - MARY,Completed,300.00,,1300.00\n"
    )

    response = upload(admin, data, name="statement.csv")

    assert (response.json["source"], response.json["added"]) == ("csv", 1)


def test_pasted_sms_adds_the_payment_and_its_charge(admin):
    text = (
        "XXXYYYZZZ9 Confirmed. Ksh80.00 sent to MSEE WA CHIPO 0704444444 on 12/11/26 at 1:57 PM. "
        "New M-PESA balance is Ksh100.00. Transaction cost, Ksh7.00."
    )

    response = admin.post("/api/money/sms", json={"text": text})

    assert response.json["added"] == 2
    rows = db.session.scalars(
        db.select(MoneyTransaction).order_by(MoneyTransaction.is_charge)
    ).all()
    assert [(r.amount, r.category, r.is_charge) for r in rows] == [
        (Decimal("80.00"), "other_expense", False),
        (Decimal("7.00"), "fees", True),
    ]
    assert (
        admin.post("/api/money/sms", json={"text": "hello there, nothing here"}).status_code == 422
    )


def test_a_new_category_is_remembered_for_that_person(admin):
    upload(admin, statement_pdf(ROWS))
    bob = by_receipt()["TAQ1AAAAAE"]
    later = [
        "TAQ1AAAAAF 2026-11-03 11:00:00 Customer Transfer to - 0700***111 BOB COMPLETED"
        " 0.00 100.00 43.00"
    ]

    changed = admin.put(
        f"/api/money/transactions/{bob.id}", json={"category": "wages", "remember": True}
    )
    upload(admin, statement_pdf(later))

    assert changed.json["transaction"]["category"] == "wages"
    assert db.session.scalar(db.select(CategoryRule.category)) == "wages"
    assert by_receipt()["TAQ1AAAAAF"].category == "wages"


def test_remembering_updates_earlier_payments_to_the_same_person(admin):
    rows = ROWS + [
        "TAQ1AAAAAG 2026-11-04 11:00:00 Customer Transfer to - 0700***111 BOB COMPLETED"
        " 0.00 100.00 43.00"
    ]
    upload(admin, statement_pdf(rows))
    first = by_receipt()["TAQ1AAAAAE"]

    changed = admin.put(f"/api/money/transactions/{first.id}", json={"category": "wages"})

    assert changed.json["also_changed"] == 1
    assert by_receipt()["TAQ1AAAAAG"].category == "wages"


def test_categories_must_match_the_direction(admin):
    upload(admin, statement_pdf(ROWS))
    money_in = by_receipt()["TAQ1AAAAAA"]

    refused = admin.put(f"/api/money/transactions/{money_in.id}", json={"category": "rent"})

    assert refused.status_code == 422


def test_payments_already_rung_up_at_the_till_are_linked(admin, as_role):
    seller = as_role("sales")
    category = Category(name="Drinks")
    db.session.add(category)
    db.session.flush()
    db.session.add(
        Product(
            sku="T",
            name="Tea",
            category_id=category.id,
            cost_price=Decimal("50"),
            selling_price=Decimal("300"),
            quantity=5,
        )
    )
    db.session.commit()
    payment = seller.post(
        "/api/payments/mpesa",
        json={
            "phone": "0712345678",
            "items": [{"product_id": 1, "quantity": 1}],
            "idempotency_key": "linking-sale-1",
        },
    ).json
    seller.post(f"/api/payments/mpesa/{payment['id']}/simulate", json={"outcome": "paid"})
    receipt = db.session.scalar(db.select(Sale.payment_reference))
    rows = [
        f"{receipt} 2026-11-02 08:00:00 Merchant Customer Payment from 0712***678 - MARY"
        " COMPLETED 300.00 0.00 1,300.00"
    ]

    upload(admin, statement_pdf(rows))

    linked = by_receipt()[receipt]
    assert linked.sale_id is not None
    assert linked.category == "sales"


def test_transactions_can_be_filtered_and_searched(admin):
    upload(admin, statement_pdf(ROWS))

    money_in = admin.get("/api/money/transactions?direction=in").json
    fees = admin.get("/api/money/transactions?category=fees").json
    kplc = admin.get("/api/money/transactions?search=kplc").json
    imports = admin.get("/api/money/imports").json
    in_import = admin.get(f"/api/money/transactions?import_id={imports['results'][0]['id']}").json

    assert [t["receipt"] for t in money_in["results"]] == ["TAQ1AAAAAA"]
    assert fees["count"] == 1
    assert kplc["results"][0]["counterparty"] == "KPLC PREPAID"
    assert in_import["count"] == 5


def test_an_import_can_be_undone(admin):
    batch = upload(admin, statement_pdf(ROWS)).json

    assert admin.delete(f"/api/money/imports/{batch['id']}").status_code == 204
    assert db.session.scalar(db.select(db.func.count()).select_from(MoneyTransaction)) == 0
    assert upload(admin, statement_pdf(ROWS)).json["added"] == 5


def test_the_category_lists_are_published(admin):
    lists = admin.get("/api/money/categories").json

    assert lists["money_in"][0] == "sales"
    assert "stock" in lists["money_out"]
