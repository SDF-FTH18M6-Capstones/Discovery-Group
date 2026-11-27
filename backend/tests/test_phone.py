from app.extensions import db
from app.models import Business, MoneyImport, MoneyTransaction, PhoneLink
from app.tenancy import tenant

RECEIVED = (
    "UKR1ABCDE1 Confirmed.You have received Ksh500.00 from DEBRA PANTHER 0759123513 on "
    "27/11/26 at 6:40 PM New M-PESA balance is Ksh1,500.00."
)
SENT = (
    "UKR1ABCDE2 Confirmed. Ksh80.00 sent to MSEE WA CHIPO 0704444444 on 27/11/26 at 1:57 PM. "
    "New M-PESA balance is Ksh1,420.00. Transaction cost, Ksh7.00."
)


def link(admin):
    return admin.post("/api/phone/link").json["url"].split("localhost", 1)[1]


def test_a_linked_phone_sends_messages_straight_in(admin, client):
    path = link(admin)

    first = client.post(path, json={"from": "MPESA", "text": RECEIVED})
    second = client.post(path, json={"from": "MPESA", "text": SENT})

    assert (first.json, second.json) == (
        {"added": 1, "ignored": False},
        {"added": 2, "ignored": False},
    )
    batches = db.session.scalars(db.select(MoneyImport)).all()
    assert [(b.source, b.added) for b in batches] == [("phone", 3)]
    rows = {t.receipt: t.category for t in db.session.scalars(db.select(MoneyTransaction))}
    assert rows["UKR1ABCDE1"] == "sales"
    status = admin.get("/api/phone/link").json
    assert (status["active"], status["messages"], status["url"]) == (True, 2, None)
    assert status["last_message_at"] is not None


def test_the_same_message_twice_is_only_counted_once(admin, client):
    path = link(admin)

    client.post(path, json={"from": "MPESA", "text": RECEIVED})
    again = client.post(path, json={"from": "MPESA", "text": RECEIVED})

    assert again.json["added"] == 0
    assert db.session.scalar(db.select(db.func.count(MoneyTransaction.id))) == 1


def test_other_messages_are_ignored(admin, client):
    path = link(admin)

    from_friend = client.post(path, json={"from": "0712000000", "text": RECEIVED})
    chatter = client.post(path, json={"from": "M-PESA", "text": "Dial *334# for offers"})
    plain = client.post(path, data=RECEIVED, content_type="text/plain")
    form = client.post(path, data={"sender": "MPESA", "message": SENT})

    assert from_friend.json == {"added": 0, "ignored": True}
    assert chatter.json == {"added": 0, "ignored": True}
    assert plain.json["added"] == 1
    assert form.json["added"] == 2


def test_wrong_or_old_links_are_refused(admin, client):
    old = link(admin)
    new = link(admin)

    assert client.post(old, json={"text": RECEIVED}).status_code == 404
    assert client.post("/api/phone/inbox/made-up", json={"text": RECEIVED}).status_code == 404
    assert client.post(new, json={"text": RECEIVED}).status_code == 200

    assert admin.delete("/api/phone/link").status_code == 204
    assert client.post(new, json={"text": RECEIVED}).status_code == 404
    assert admin.get("/api/phone/link").json == {"active": False, "url": None, "messages": 0}


def test_only_the_token_hash_is_stored(admin):
    url = admin.post("/api/phone/link").json["url"]
    token = url.rsplit("/", 1)[1]

    stored = db.session.scalar(db.select(PhoneLink.token_hash))
    assert token not in stored and len(stored) == 64


def test_links_stay_inside_their_business(admin, client):
    other = Business(name="Other Shop", join_code="OTHER123")
    db.session.add(other)
    db.session.commit()

    client.post(link(admin), json={"from": "MPESA", "text": RECEIVED})

    with tenant(other.id):
        assert db.session.scalar(db.select(db.func.count(MoneyTransaction.id))) == 0
    with tenant(admin.user.business_id):
        assert db.session.scalar(db.select(db.func.count(MoneyTransaction.id))) == 1
