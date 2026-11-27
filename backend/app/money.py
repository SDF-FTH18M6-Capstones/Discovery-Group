from datetime import UTC
from zoneinfo import ZoneInfo

from app.extensions import db
from app.models import CategoryRule, MoneyImport, MoneyTransaction, Sale, Supplier

UTILITIES = ("kplc", "nairobi water", "water company", "zuku", "safaricom home", "gotv", "dstv")
DEFAULTS = {
    ("in", "customer_payment"): "sales",
    ("in", "received"): "sales",
    ("in", "deposit"): "owner_deposit",
    ("in", "loan"): "loan",
    ("out", "fee"): "fees",
    ("out", "withdrawal"): "withdrawal",
    ("out", "airtime"): "airtime",
    ("out", "loan"): "loan_repayment",
}


def rule_key(counterparty, phone):
    return (phone or counterparty or "").strip().lower()[:120]


def suggest(entry, rules, suppliers):
    key = rule_key(entry.counterparty, entry.phone)
    if (entry.direction, key) in rules:
        return rules[(entry.direction, key)]
    if (entry.direction, entry.kind) in DEFAULTS:
        return DEFAULTS[(entry.direction, entry.kind)]
    if entry.direction == "in":
        return "other_income"
    name = (entry.counterparty or "").lower()
    if any(word in name for word in UTILITIES):
        return "utilities"
    if name and any(supplier in name or name in supplier for supplier in suppliers):
        return "stock"
    return "other_expense"


def local_time(moment, timezone):
    return moment.replace(tzinfo=ZoneInfo(timezone)).astimezone(UTC)


def import_entries(entries, skipped, source, filename, user):
    timezone = user.business.timezone
    rules = {
        (rule.direction, rule.match): rule.category
        for rule in db.session.scalars(db.select(CategoryRule))
    }
    suppliers = [name.lower() for name in db.session.scalars(db.select(Supplier.name)) if name]
    known = set(
        db.session.execute(db.select(MoneyTransaction.receipt, MoneyTransaction.is_charge)).all()
    )
    sales = dict(
        db.session.execute(
            db.select(Sale.payment_reference, Sale.id).where(Sale.payment_reference.is_not(None))
        ).all()
    )
    batch = MoneyImport(
        source=source,
        filename=filename,
        added=0,
        duplicates=0,
        skipped=skipped,
        created_by=user.id,
    )
    db.session.add(batch)
    rows = []
    for entry in entries:
        rows.append((entry, entry.kind == "fee"))
        if entry.extra.get("fee"):
            rows.append((entry, True))
    for entry, is_charge in rows:
        if (entry.receipt, is_charge) in known:
            batch.duplicates += 1
            continue
        known.add((entry.receipt, is_charge))
        charge_only = is_charge and entry.kind != "fee"
        transaction = MoneyTransaction(
            receipt=entry.receipt,
            is_charge=is_charge,
            occurred_at=local_time(entry.occurred_at, timezone),
            direction="out" if charge_only else entry.direction,
            amount=entry.extra["fee"] if charge_only else entry.amount,
            balance=None if charge_only else entry.balance,
            kind="fee" if is_charge else entry.kind,
            category="fees" if is_charge else suggest(entry, rules, suppliers),
            counterparty="M-Pesa charges" if is_charge else entry.counterparty,
            phone=None if is_charge else entry.phone,
            details=entry.details,
            sale_id=None if is_charge else sales.get(entry.receipt),
        )
        if transaction.sale_id:
            transaction.category = "sales"
        batch.transactions.append(transaction)
        batch.added += 1
    times = [t.occurred_at for t in batch.transactions]
    batch.first_at = min(times, default=None)
    batch.last_at = max(times, default=None)
    return batch


def remember(transaction, category):
    key = rule_key(transaction.counterparty, transaction.phone)
    if not key or transaction.is_charge:
        return 0
    rule = db.session.scalar(
        db.select(CategoryRule).where(
            CategoryRule.direction == transaction.direction, CategoryRule.match == key
        )
    )
    if rule is None:
        db.session.add(CategoryRule(direction=transaction.direction, match=key, category=category))
    else:
        rule.category = category
    same = db.select(MoneyTransaction).where(
        MoneyTransaction.direction == transaction.direction,
        MoneyTransaction.is_charge.is_(False),
        MoneyTransaction.sale_id.is_(None),
        db.or_(
            db.func.lower(MoneyTransaction.phone) == key,
            db.func.lower(MoneyTransaction.counterparty) == key,
        ),
    )
    changed = 0
    for other in db.session.scalars(same):
        if other.category != category:
            other.category = category
            changed += 1
    return changed
