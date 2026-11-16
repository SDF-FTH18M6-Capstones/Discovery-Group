"""Helpers shared by every resource: pagination, find-or-404, safe save and delete."""

import math

from flask_smorest import abort
from marshmallow import Schema, fields, validate
from sqlalchemy.exc import IntegrityError

from app.extensions import db


class PageQuery(Schema):
    """?page=1&per_page=20 on every list endpoint."""

    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))


def page_schema(item_schema):
    """Response shape for a paginated list."""
    return Schema.from_dict(
        {
            "results": fields.List(fields.Nested(item_schema)),
            "count": fields.Integer(),
            "page": fields.Integer(),
            "per_page": fields.Integer(),
            "pages": fields.Integer(),
        },
        name=f"{item_schema.__name__.removesuffix('Schema')}Page",
    )


def paginate(query, page, per_page):
    count = db.session.scalar(db.select(db.func.count()).select_from(query.subquery()))
    results = db.session.scalars(query.limit(per_page).offset((page - 1) * per_page)).all()
    return {
        "results": results,
        "count": count,
        "page": page,
        "per_page": per_page,
        "pages": math.ceil(count / per_page) if count else 0,
    }


def get_or_404(model, item_id):
    item = db.session.get(model, item_id)
    if item is None:
        abort(404, message=f"{model.__name__} {item_id} not found")
    return item


def save(item, conflict_message):
    """Insert or update; a unique or foreign-key clash becomes a 409 instead of a 500."""
    db.session.add(item)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(409, message=conflict_message)
    return item


def delete(item, in_use_message):
    db.session.delete(item)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(409, message=in_use_message)