#Keeps every business's data apart.
from contextlib import contextmanager

from flask import g, has_app_context
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, with_loader_criteria

from app.models.base import TenantMixin, reference
from app.models.business import DocumentCounter


def current_business_id():
    if not has_app_context():
        return None
    return g.get("business_id")


def set_business(business_id):
    g.business_id = business_id


def clear_business():
    if has_app_context():
        g.pop("business_id", None)


@contextmanager
def tenant(business_id):
    previous = current_business_id()
    set_business(business_id)
    try:
        yield
    finally:
        if previous is None:
            clear_business()
        else:
            set_business(previous)


def scoped(statement):
    business_id = current_business_id()
    if business_id is None:
        return statement
    return statement.options(
        with_loader_criteria(
            TenantMixin, lambda cls: cls.business_id == business_id, include_aliases=True
        )
    )


@event.listens_for(Session, "do_orm_execute")
def _only_this_business(state):
    business_id = current_business_id()
    if business_id is None or state.execution_options.get("all_businesses"):
        return
    if state.is_column_load or state.is_relationship_load:
        return
    if state.is_select or state.is_update or state.is_delete:
        state.statement = state.statement.options(
            with_loader_criteria(
                TenantMixin, lambda cls: cls.business_id == business_id, include_aliases=True
            )
        )


def next_number(connection, business_id, kind):
    statement = (
        pg_insert(DocumentCounter.__table__)
        .values(business_id=business_id, kind=kind, last=1)
        .on_conflict_do_update(
            index_elements=["business_id", "kind"],
            set_={"last": DocumentCounter.__table__.c.last + 1},
        )
        .returning(DocumentCounter.__table__.c.last)
    )
    return connection.execute(statement).scalar_one()


@event.listens_for(Session, "before_flush")
def _stamp_new_rows(session, _flush_context, _instances):
    business_id = current_business_id()
    for obj in list(session.new):
        if not isinstance(obj, TenantMixin):
            continue
        if obj.business_id is None:
            if business_id is None:
                raise RuntimeError(
                    f"Cannot save a new {type(obj).__name__} without a business. "
                    "Use `with tenant(business_id):`."
                )
            obj.business_id = business_id
        kind = getattr(type(obj), "__number_kind__", None)
        if kind and obj.number is None:
            obj.number = next_number(session.connection(), obj.business_id, kind)
            _fill_derived_codes(obj)


def _fill_derived_codes(obj):
    if type(obj).__name__ == "Asset":
        if not obj.asset_code:
            obj.asset_code = reference("AST", obj.number)
        if not obj.barcode:
            obj.barcode = f"SP{obj.business_id:04d}{obj.number:06d}"


__all__ = [
    "clear_business",
    "current_business_id",
    "next_number",
    "scoped",
    "set_business",
    "tenant",
]
