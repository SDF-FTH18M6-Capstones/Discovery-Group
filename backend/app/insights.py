import math
from collections import defaultdict
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from statistics import pstdev
from zoneinfo import ZoneInfo

from app.extensions import db
from app.models import (
    Expense,
    MoneyTransaction,
    MpesaPayment,
    Product,
    Sale,
    SaleItem,
)
from app.models.money import TRANSFERS

HISTORY_DAYS = 84
FIT_DAYS = 28
PATTERN_DAYS = 56
MIN_DAYS = 14
HORIZON = 14
ALPHA = 0.3
RANGE = 1.28
LEAD_DAYS = 7


def shop_dates(business):
    zone = ZoneInfo(business.timezone)
    today = datetime.now(zone).date()
    return zone, today


def day_start(day, zone):
    return datetime.combine(day, time.min, zone).astimezone(UTC)


def daily_takings(business, days=HISTORY_DAYS):
    zone, today = shop_dates(business)
    since = day_start(today - timedelta(days=days), zone)
    totals = defaultdict(Decimal)
    for created, total in db.session.execute(
        db.select(Sale.created_at, Sale.total).where(
            Sale.status == "completed", Sale.created_at >= since
        )
    ):
        totals[created.astimezone(zone).date()] += total
    for occurred, amount in db.session.execute(
        db.select(MoneyTransaction.occurred_at, MoneyTransaction.amount).where(
            MoneyTransaction.direction == "in",
            MoneyTransaction.category == "sales",
            MoneyTransaction.sale_id.is_(None),
            MoneyTransaction.occurred_at >= since,
        )
    ):
        totals[occurred.astimezone(zone).date()] += amount
    return totals, today


def series(totals, today):
    days = sorted(day for day in totals if day < today)
    if not days:
        return []
    start = days[0]
    return [
        (start + timedelta(days=n), float(totals.get(start + timedelta(days=n), 0)))
        for n in range((today - start).days)
    ]


def weekday_factors(history):
    level = sum(value for _, value in history) / len(history) if history else 0
    factors = {}
    for weekday in range(7):
        values = [value for day, value in history if day.weekday() == weekday]
        if not values or not level:
            factors[weekday] = 1.0
            continue
        raw = (sum(values) / len(values)) / level
        factors[weekday] = (raw * len(values) + 1.0) / (len(values) + 1)
    return factors


def fit(history):
    window = history[-FIT_DAYS:]
    factors = weekday_factors(history[-PATTERN_DAYS:])
    level = None
    errors = []
    for day, value in window:
        factor = factors[day.weekday()] or 1.0
        if level is not None:
            errors.append(value - level * factor)
        plain = value / factor
        level = plain if level is None else ALPHA * plain + (1 - ALPHA) * level
    spread = pstdev(errors) if len(errors) > 1 else 0.0
    return level or 0.0, factors, spread


def predict(history, start, days):
    level, factors, spread = fit(history)
    points = []
    for n in range(days):
        day = start + timedelta(days=n)
        expected = max(0.0, level * factors[day.weekday()])
        points.append(
            {
                "date": day,
                "expected": expected,
                "low": max(0.0, expected - RANGE * spread),
                "high": expected + RANGE * spread,
            }
        )
    return points


def accuracy(history):
    if len(history) < MIN_DAYS + HORIZON:
        return None
    train, test = history[:-HORIZON], history[-HORIZON:]
    guesses = predict(train, test[0][0], HORIZON)
    actual = sum(value for _, value in test)
    if not actual:
        return None
    missed = sum(
        abs(value - guess["expected"]) for (_, value), guess in zip(test, guesses, strict=True)
    )
    return max(0, round(100 * (1 - missed / actual)))


def sales_outlook(business):
    totals, today = daily_takings(business)
    history = series(totals, today)
    recent = history[-56:]
    result = {
        "history": [{"date": day, "takings": round(value, 2)} for day, value in recent],
        "forecast": [],
        "accuracy": None,
        "ready": len(history) >= MIN_DAYS,
        "days_of_history": len(history),
        "comparisons": comparisons(history, totals, today),
    }
    if result["ready"]:
        result["forecast"] = [
            {key: round(value, 2) if key != "date" else value for key, value in point.items()}
            for point in predict(history, today, HORIZON)
        ]
        result["accuracy"] = accuracy(history)
    return result


def comparisons(history, totals, today):
    notes = []
    if not history:
        return notes
    yesterday, value = history[-1]
    same_days = [v for day, v in history[-29:-1] if day.weekday() == yesterday.weekday()]
    if same_days and sum(same_days):
        usual = sum(same_days) / len(same_days)
        change = round(100 * (value - usual) / usual)
        notes.append(
            {
                "key": "yesterday",
                "value": round(value, 2),
                "usual": round(usual, 2),
                "change": change,
            }
        )
    so_far = range(today.weekday() + 1)
    this_week = sum(float(totals.get(today - timedelta(days=n), 0)) for n in so_far)
    last_week = sum(float(totals.get(today - timedelta(days=7 + n), 0)) for n in so_far)
    if last_week:
        notes.append(
            {
                "key": "week",
                "value": round(this_week, 2),
                "usual": round(last_week, 2),
                "change": round(100 * (this_week - last_week) / last_week),
            }
        )
    month = [(day, v) for day, v in history if day >= today.replace(day=1)]
    if month:
        best_day, best = max(month, key=lambda item: item[1])
        if best:
            notes.append({"key": "best_day", "date": best_day, "value": round(best, 2)})
    return notes


def stock_outlook():
    month_ago = datetime.now(UTC) - timedelta(days=30)
    recent = (
        db.select(SaleItem)
        .join(SaleItem.sale)
        .where(Sale.status == "completed", Sale.created_at >= month_ago)
    )
    sold_month = dict(
        db.session.execute(
            recent.with_only_columns(SaleItem.product_id, db.func.sum(SaleItem.quantity)).group_by(
                SaleItem.product_id
            )
        ).all()
    )
    gain = db.func.sum((SaleItem.unit_price - SaleItem.unit_cost) * SaleItem.quantity)
    profit = db.session.execute(
        recent.with_only_columns(Product.id, Product.name, gain, db.func.sum(SaleItem.quantity))
        .join(SaleItem.product)
        .group_by(Product.id, Product.name)
        .order_by(gain.desc())
        .limit(5)
    ).all()
    products = db.session.scalars(db.select(Product).where(Product.is_active.is_(True))).all()
    running_out, slow = [], []
    for product in products:
        per_day = (sold_month.get(product.id) or 0) / 30
        if per_day and product.quantity > 0:
            days_left = product.quantity / per_day
            if days_left <= LEAD_DAYS:
                running_out.append(
                    {
                        "id": product.id,
                        "name": product.name,
                        "quantity": product.quantity,
                        "per_day": round(per_day, 1),
                        "days_left": math.floor(days_left),
                        "suggested_order": max(1, math.ceil(per_day * 14 - product.quantity)),
                    }
                )
        old_enough = product.created_at and product.created_at <= month_ago
        if product.quantity > 0 and not sold_month.get(product.id) and old_enough:
            slow.append(
                {
                    "id": product.id,
                    "name": product.name,
                    "quantity": product.quantity,
                    "tied_up": round(float(product.cost_price * product.quantity), 2),
                }
            )
    return {
        "running_out": sorted(running_out, key=lambda item: item["days_left"])[:8],
        "slow_movers": sorted(slow, key=lambda item: -item["tied_up"])[:5],
        "most_profitable": [
            {"id": pid, "name": name, "profit": round(float(earned), 2), "sold": int(quantity)}
            for pid, name, earned, quantity in profit
        ],
    }


def customer_outlook():
    now = datetime.now(UTC)
    since = now - timedelta(days=180)
    people = {}

    def add(key, name, phone, amount, when):
        person = people.setdefault(
            key, {"name": name, "phone": phone, "total": 0.0, "visits": 0, "last_at": when}
        )
        if when >= now - timedelta(days=90):
            person["total"] += float(amount)
        person["visits"] += 1
        person["last_at"] = max(person["last_at"], when)
        person["name"] = person["name"] or name

    for name, phone, amount, when in db.session.execute(
        db.select(
            MoneyTransaction.counterparty,
            MoneyTransaction.phone,
            MoneyTransaction.amount,
            MoneyTransaction.occurred_at,
        ).where(
            MoneyTransaction.direction == "in",
            MoneyTransaction.category == "sales",
            MoneyTransaction.occurred_at >= since,
        )
    ):
        key = (phone or name or "").lower()
        if key:
            add(key, name, phone, amount, when)
    for phone, amount, when in db.session.execute(
        db.select(MpesaPayment.phone, MpesaPayment.amount, MpesaPayment.completed_at).where(
            MpesaPayment.purpose == "sale",
            MpesaPayment.status == "paid",
            MpesaPayment.completed_at >= since,
        )
    ):
        add(phone, None, phone, amount, when)
    everyone = list(people.values())
    top = sorted((p for p in everyone if p["total"]), key=lambda p: -p["total"])[:5]
    quiet = sorted(
        (p for p in everyone if p["visits"] >= 3 and p["last_at"] < now - timedelta(days=30)),
        key=lambda p: -p["visits"],
    )[:5]
    return {"top": top, "gone_quiet": quiet}


def cash_outlook(business, sales):
    zone, today = shop_dates(business)
    since = day_start(today - timedelta(days=60), zone)
    spent = sum(
        (
            amount
            for (amount,) in db.session.execute(
                db.select(MoneyTransaction.amount).where(
                    MoneyTransaction.direction == "out",
                    MoneyTransaction.category.not_in(TRANSFERS),
                    MoneyTransaction.occurred_at >= since,
                )
            )
        ),
        Decimal(0),
    )
    spent += db.session.scalar(
        db.select(db.func.coalesce(db.func.sum(Expense.amount), 0)).where(
            Expense.spent_on >= today - timedelta(days=60)
        )
    )
    other_in = db.session.scalar(
        db.select(db.func.coalesce(db.func.sum(MoneyTransaction.amount), 0)).where(
            MoneyTransaction.direction == "in",
            MoneyTransaction.category.not_in(("sales", *TRANSFERS)),
            MoneyTransaction.occurred_at >= since,
        )
    )
    weeks = weekly_flow(zone, today)
    latest = db.session.execute(
        db.select(MoneyTransaction.balance, MoneyTransaction.occurred_at)
        .where(MoneyTransaction.balance.is_not(None))
        .order_by(MoneyTransaction.occurred_at.desc(), MoneyTransaction.id.desc())
        .limit(1)
    ).first()
    result = {
        "weeks": weeks,
        "ready": sales["ready"],
        "expected_in": None,
        "expected_out": None,
        "expected_net": None,
        "balance": float(latest[0]) if latest else None,
        "balance_at": latest[1] if latest else None,
        "projected_balance": None,
    }
    if not sales["ready"]:
        return result
    totals, _ = daily_takings(business)
    history = series(totals, today)
    takings = sum(point["expected"] for point in predict(history, today, 30))
    expected_in = takings + float(other_in) / 2
    expected_out = float(spent) / 2
    result.update(
        expected_in=round(expected_in, 2),
        expected_out=round(expected_out, 2),
        expected_net=round(expected_in - expected_out, 2),
    )
    if latest:
        result["projected_balance"] = round(float(latest[0]) + expected_in - expected_out, 2)
    return result


def weekly_flow(zone, today):
    start = today - timedelta(days=today.weekday() + 7 * 7)
    since = day_start(start, zone)
    weeks = {start + timedelta(days=7 * n): {"in": 0.0, "out": 0.0} for n in range(8)}

    def week_of(moment):
        day = moment.astimezone(zone).date()
        return day - timedelta(days=day.weekday())

    for created, total in db.session.execute(
        db.select(Sale.created_at, Sale.total).where(
            Sale.status == "completed", Sale.created_at >= since
        )
    ):
        weeks.setdefault(week_of(created), {"in": 0.0, "out": 0.0})["in"] += float(total)
    for occurred, direction, amount, category, sale_id in db.session.execute(
        db.select(
            MoneyTransaction.occurred_at,
            MoneyTransaction.direction,
            MoneyTransaction.amount,
            MoneyTransaction.category,
            MoneyTransaction.sale_id,
        ).where(MoneyTransaction.occurred_at >= since)
    ):
        if category in TRANSFERS or sale_id:
            continue
        weeks.setdefault(week_of(occurred), {"in": 0.0, "out": 0.0})[direction] += float(amount)
    for spent_on, amount in db.session.execute(
        db.select(Expense.spent_on, Expense.amount).where(Expense.spent_on >= start)
    ):
        monday = spent_on - timedelta(days=spent_on.weekday())
        weeks.setdefault(monday, {"in": 0.0, "out": 0.0})["out"] += float(amount)
    return [
        {"week": week, "in": round(flow["in"], 2), "out": round(flow["out"], 2)}
        for week, flow in sorted(weeks.items())
        if week >= start
    ]


def build(business):
    sales = sales_outlook(business)
    return {
        "sales": sales,
        "stock": stock_outlook(),
        "customers": customer_outlook(),
        "cash": cash_outlook(business, sales),
    }
