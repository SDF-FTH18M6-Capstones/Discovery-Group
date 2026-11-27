import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from flask import current_app

TRIAL_DAYS = 14
GRACE_DAYS = 7
PLANS = (1, 3, 6, 12)


def business_today(business):
    return datetime.now(ZoneInfo(business.timezone)).date()


def add_months(day, months):
    month = day.month - 1 + months
    year, month = day.year + month // 12, month % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def trial_end(business):
    if business.trial_ends_on:
        return business.trial_ends_on
    started = business.created_at.date() if business.created_at else date.today()
    return started + timedelta(days=TRIAL_DAYS)


def subscription(business):
    today = business_today(business)
    trial = trial_end(business)
    ends = max(filter(None, (trial, business.paid_until)))
    grace_until = ends + timedelta(days=GRACE_DAYS)
    if business.paid_until and today <= business.paid_until:
        status = "active"
    elif today <= trial:
        status = "trial"
    elif today <= grace_until:
        status = "grace"
    else:
        status = "expired"
    required = current_app.config["SUBSCRIPTIONS_REQUIRED"]
    return {
        "status": status,
        "required": required,
        "trial_ends_on": trial,
        "paid_until": business.paid_until,
        "ends_on": ends,
        "grace_until": grace_until,
        "days_left": (ends - today).days,
        "read_only": required and status == "expired",
        "price": current_app.config["SUBSCRIPTION_PRICE"],
    }


def read_only(business):
    return subscription(business)["read_only"]


def extend(business, months):
    today = business_today(business)
    start = max(filter(None, (today, trial_end(business), business.paid_until)))
    business.paid_until = add_months(start, months)
    return business.paid_until
