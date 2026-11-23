from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from flask import current_app, g, has_app_context

from app.extensions import db

DEFAULT_ZONE = "Africa/Nairobi"


def current_business():
    from app.models import Business
    from app.tenancy import current_business_id

    business_id = current_business_id()
    if business_id is None:
        return None
    cached = g.get("business")
    if cached is not None and cached.id == business_id:
        return cached
    business = db.session.get(Business, business_id)
    g.business = business
    return business


def shop_zone_name():
    business = current_business() if has_app_context() else None
    if business is not None and business.timezone:
        return business.timezone
    return current_app.config.get("SHOP_TIMEZONE", DEFAULT_ZONE)


def shop_zone():
    return ZoneInfo(shop_zone_name())


def shop_today():
    return datetime.now(shop_zone()).date()


def day_bounds(day: date):
    start = datetime.combine(day, time.min, tzinfo=shop_zone())
    return start, start + timedelta(days=1)


def range_bounds(date_from: date, date_to: date):
    start, _ = day_bounds(date_from)
    _, end = day_bounds(date_to)
    return start, end


def shop_day(column):
    return db.func.date(db.func.timezone(shop_zone_name(), column))
