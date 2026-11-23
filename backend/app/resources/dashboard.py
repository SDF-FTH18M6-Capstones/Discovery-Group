from flask_jwt_extended import current_user
from flask_smorest import Blueprint
from marshmallow import fields

from app.auth import roles_required
from app.extensions import db
from app.models import Asset, AssetAssignment, Product, Purchase, Repair, Request, Sale
from app.models.assets import OPEN_REPAIR_STATUSES
from app.schemas import Schema
from app.shoptime import day_bounds, shop_today
from app.tenancy import scoped

blp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard", description="Dashboard")

TILES_FOR = {
    "admin": ("low_stock", "approvals", "awaiting_receipt", "open_repairs", "sales_today"),
    "procurement": ("approvals", "awaiting_receipt", "my_requests"),
    "inventory": ("low_stock", "awaiting_receipt", "open_repairs", "overdue_assets"),
    "sales": ("my_sales_today", "my_requests", "my_assets"),
    "employee": ("my_requests", "my_assets", "my_repairs"),
}


class TileOut(Schema):
    key = fields.String()
    label = fields.String()
    count = fields.Integer()
    detail = fields.String(allow_none=True)
    amount = fields.Decimal(places=2, as_string=True, allow_none=True)
    link = fields.String()
    tone = fields.String()


class PulseOut(Schema):
    role = fields.String()
    tiles = fields.List(fields.Nested(TileOut))


def count(statement):
    return (
        db.session.scalar(db.select(db.func.count()).select_from(scoped(statement).subquery())) or 0
    )


def tile(key, label, n, link, detail=None, amount=None, warn_when=1, danger=None):
    tone = "ok"
    if danger is not None and danger:
        tone = "danger"
    elif n >= warn_when:
        tone = "warn"
    return {
        "key": key,
        "label": label,
        "count": n,
        "detail": detail,
        "amount": amount,
        "link": link,
        "tone": tone,
    }


def low_stock():
    base = db.select(Product.id).where(
        Product.is_active.is_(True), Product.quantity <= Product.reorder_level
    )
    n = count(base)
    out = count(base.where(Product.quantity == 0))
    return tile(
        "low_stock",
        "Low stock",
        n,
        "/products?low_stock=1",
        f"{out} out of stock" if out else None,
        danger=out,
    )


def approvals():
    base = db.select(Request.id).where(Request.status == "pending")
    if current_user.role == "procurement":
        base = base.where(Request.requester_id != current_user.id)
    n = count(base)
    urgent = count(base.where(Request.urgency == "urgent"))
    return tile(
        "approvals",
        "Pending approvals",
        n,
        "/approvals",
        f"{urgent} urgent" if urgent else None,
        danger=urgent,
    )


def awaiting_receipt():
    base = db.select(Purchase.id).where(Purchase.status.in_(("ordered", "partially_received")))
    n = count(base)
    partial = count(base.where(Purchase.status == "partially_received"))
    return tile(
        "awaiting_receipt",
        "Orders awaiting receipt",
        n,
        "/purchases?status=awaiting",
        f"{partial} partly received" if partial else None,
    )


def open_repairs():
    base = db.select(Repair.id).where(Repair.status.in_(OPEN_REPAIR_STATUSES))
    n = count(base)
    waiting = count(base.where(Repair.status == "submitted"))
    return tile(
        "open_repairs",
        "Open repairs",
        n,
        "/repairs?status=open",
        f"{waiting} not started" if waiting else None,
    )


def overdue_assets():
    n = count(
        db.select(Asset.id).where(
            Asset.current_assignment.has(AssetAssignment.expected_return < shop_today())
        )
    )
    return tile("overdue_assets", "Overdue assets", n, "/assets?overdue=1", danger=n)


def sales_today(mine=False):
    start, end = day_bounds(shop_today())
    where = [Sale.created_at >= start, Sale.created_at < end, Sale.status == "completed"]
    if mine:
        where.append(Sale.attendant_id == current_user.id)
    n, total = db.session.execute(
        db.select(db.func.count(Sale.id), db.func.coalesce(db.func.sum(Sale.total), 0)).where(
            *where
        )
    ).one()
    key, label = ("my_sales_today", "My sales today") if mine else ("sales_today", "Sales today")
    return tile(
        key, label, n, f"/sales?day={shop_today().isoformat()}", amount=total, warn_when=10**9
    )


def my_requests():
    base = db.select(Request.id).where(
        Request.requester_id == current_user.id, Request.status.in_(("pending", "approved"))
    )
    n = count(base)
    pending = count(base.where(Request.status == "pending"))
    return tile(
        "my_requests",
        "My active requests",
        n,
        "/requests?tab=active",
        f"{pending} awaiting a decision" if pending else None,
        warn_when=10**9,
    )


def my_assets():
    base = db.select(Asset.id).where(Asset.assigned_to == current_user.id)
    n = count(base)
    overdue = count(
        base.where(Asset.current_assignment.has(AssetAssignment.expected_return < shop_today()))
    )
    return tile(
        "my_assets",
        "Assets with me",
        n,
        "/assets",
        f"{overdue} overdue" if overdue else None,
        warn_when=10**9,
        danger=overdue,
    )


def my_repairs():
    n = count(
        db.select(Repair.id).where(
            Repair.reported_by == current_user.id, Repair.status.in_(OPEN_REPAIR_STATUSES)
        )
    )
    return tile("my_repairs", "My open repairs", n, "/repairs?status=open", warn_when=10**9)


BUILDERS = {
    "low_stock": low_stock,
    "approvals": approvals,
    "awaiting_receipt": awaiting_receipt,
    "open_repairs": open_repairs,
    "overdue_assets": overdue_assets,
    "sales_today": sales_today,
    "my_sales_today": lambda: sales_today(mine=True),
    "my_requests": my_requests,
    "my_assets": my_assets,
    "my_repairs": my_repairs,
}


@blp.route("/pulse")
@blp.response(200, PulseOut)
@roles_required()
def pulse():
    return {
        "role": current_user.role,
        "tiles": [BUILDERS[key]() for key in TILES_FOR[current_user.role]],
    }
