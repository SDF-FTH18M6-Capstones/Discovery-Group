from sqlalchemy import Numeric, func

from app.extensions import db

Money = Numeric(12, 2)


def in_list(column: str, values: tuple[str, ...], name: str) -> db.CheckConstraint:
    allowed = ", ".join(f"'{v}'" for v in values)
    return db.CheckConstraint(f"{column} IN ({allowed})", name=name)


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )