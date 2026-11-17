from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from flask import current_app

from app.extensions import db

DEFAULT_ZONE = "Africa/Nairobi"


def shop_zone_name():
    return current_app.config.get("SHOP_TIMEZONE", DEFAULT_ZONE)


def shop_zone():
    return ZoneInfo(shop_zone_name())


def shop_today():
    return datetime.now(shop_zone()).date()


def day_bounds(day: date):
    start = datetime.combine(day, time.min, tzinfo=shop_zone())
    return start, start + timedelta(days=1)


def shop_day(column):
    return db.func.date(db.func.timezone(shop_zone_name(), column))
