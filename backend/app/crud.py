import math

from flask_smorest import abort
from marshmallow import Schema, fields, validate
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.base import TenantMixin
from app.tenancy import current_business_id, scoped


class PageQuery(Schema):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))


_page_schemas = {}


def page_schema(item_schema):
    if item_schema in _page_schemas:
        return _page_schemas[item_schema]
    _page_schemas[item_schema] = Schema.from_dict(
        {
            "results": fields.List(fields.Nested(item_schema)),
            "count": fields.Integer(),
            "page": fields.Integer(),
            "per_page": fields.Integer(),
            "pages": fields.Integer(),
        },
        name=f"{item_schema.__name__.removesuffix('Schema')}Page",
    )
    return _page_schemas[item_schema]


def paginate(query, page, per_page):
    query = scoped(query)
    count = db.session.scalar(db.select(db.func.count()).select_from(query.subquery()))
    results = db.session.scalars(query.limit(per_page).offset((page - 1) * per_page)).all()
    return {
        "results": results,
        "count": count,
        "page": page,
        "per_page": per_page,
        "pages": math.ceil(count / per_page) if count else 0,
    }


def find(model, item_id):
    if item_id is None:
        return None
    item = db.session.get(model, item_id)
    if item is None:
        return None
    if isinstance(item, TenantMixin):
        business_id = current_business_id()
        if business_id is not None and item.business_id != business_id:
            return None
    return item


def get_or_404(model, item_id, label=None):
    item = find(model, item_id)
    if item is None:
        abort(404, message=f"{label or model.__name__} {item_id} not found")
    return item


def save(item, conflict_message):
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
