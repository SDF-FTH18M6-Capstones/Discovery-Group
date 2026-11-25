import math

from marshmallow import fields
from sqlalchemy import literal, null, union_all

from app.extensions import db
from app.models import AuditLog, StockMovement, User
from app.schemas import Schema
from app.tenancy import current_business_id

MOVEMENT_WORDS = {
    "purchase": "Received",
    "sale": "Sold",
    "adjustment": "Adjusted",
    "sale_void": "Sale voided",
}


class TimelineEntry(Schema):
    at = fields.DateTime()
    action = fields.String()
    summary = fields.String()
    change = fields.String(allow_none=True)
    reference = fields.String(allow_none=True)
    user_name = fields.String(allow_none=True)


def describe_change(changes):
    if not changes:
        return None
    if "status" in changes:
        old, new = changes["status"]
        return f"{words(old)} → {words(new)}"
    parts = []
    for key, (old, new) in changes.items():
        parts.append(
            f"{key.replace('_', ' ').capitalize()} {old if old is not None else '—'} → {new}"
        )
    return "; ".join(parts[:3])


def words(value):
    return str(value or "—").replace("_", " ").capitalize()


def audit_rows(entity_type, entity_id):
    return (
        db.select(
            AuditLog.created_at.label("at"),
            AuditLog.action.label("action"),
            AuditLog.summary.label("summary"),
            AuditLog.changes.label("changes"),
            null().label("change"),
            null().label("reference"),
            User.full_name.label("user_name"),
            AuditLog.id.label("sort_id"),
            literal("a").label("source"),
        )
        .outerjoin(User, User.id == AuditLog.user_id)
        .where(
            AuditLog.business_id == current_business_id(),
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == entity_id,
        )
    )


def movement_rows(product_id):
    return (
        db.select(
            StockMovement.created_at.label("at"),
            StockMovement.type.label("action"),
            db.func.coalesce(StockMovement.reason, "").label("summary"),
            null().label("changes"),
            db.func.concat(
                db.case((StockMovement.change > 0, "+"), else_=""),
                StockMovement.change,
                " (now ",
                StockMovement.quantity_after,
                ")",
            ).label("change"),
            StockMovement.reference.label("reference"),
            User.full_name.label("user_name"),
            StockMovement.id.label("sort_id"),
            literal("m").label("source"),
        )
        .join(User, User.id == StockMovement.user_id)
        .where(
            StockMovement.business_id == current_business_id(),
            StockMovement.product_id == product_id,
        )
    )


def run(statement, page, per_page):
    union = statement.subquery()
    count = db.session.scalar(db.select(db.func.count()).select_from(union))
    rows = db.session.execute(
        db.select(union)
        .order_by(union.c.at.desc(), union.c.source.desc(), union.c.sort_id.desc())
        .limit(per_page)
        .offset((page - 1) * per_page)
    ).all()
    results = []
    for row in rows:
        if row.source == "m":
            action = MOVEMENT_WORDS.get(row.action, row.action)
            change = row.change
        else:
            action = words(row.action)
            change = describe_change(row.changes)
        results.append(
            {
                "at": row.at,
                "action": action,
                "summary": row.summary,
                "change": change,
                "reference": row.reference,
                "user_name": row.user_name,
            }
        )
    return {
        "results": results,
        "count": count,
        "page": page,
        "per_page": per_page,
        "pages": math.ceil(count / per_page) if count else 0,
    }


def product_timeline(product_id, page, per_page):
    return run(
        union_all(audit_rows("product", product_id), movement_rows(product_id)), page, per_page
    )


def record_timeline(entity_type, entity_id, page, per_page):
    return run(audit_rows(entity_type, entity_id), page, per_page)
