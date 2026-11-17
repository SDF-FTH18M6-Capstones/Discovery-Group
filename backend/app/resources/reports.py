"""/api/reports — figures for the Administrator, worked out from the sales, purchase and
stock tables. "estimated_profit" uses each product's current cost price."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from flask_smorest import Blueprint
from marshmallow import fields, validate

from app.auth import roles_required
from app.extensions import db
from app.models import Product, Purchase, Sale, SaleItem
from app.schemas import Schema

blp = Blueprint("reports", __name__, url_prefix="/api/reports", description="Reports (Admin)")

money = {"places": 2, "as_string": True}


class ReportQuery(Schema):
    days = fields.Integer(load_default=7, validate=validate.Range(min=1, max=365))


class DayOut(Schema):
    day = fields.Date()
    total = fields.Decimal(**money)
    count = fields.Integer()


class TopProductOut(Schema):
    product_id = fields.Integer()
    name = fields.String()
    quantity = fields.Integer()
    total = fields.Decimal(**money)


class LowStockOut(Schema):
    id = fields.Integer()
    name = fields.String()
    quantity = fields.Integer()
    reorder_level = fields.Integer()


class SummaryOut(Schema):
    days = fields.Integer()
    date_from = fields.Date()
    date_to = fields.Date()
    sales_total = fields.Decimal(**money)
    sales_count = fields.Integer()
    average_sale = fields.Decimal(**money)
    estimated_profit = fields.Decimal(**money)
    purchases_received_total = fields.Decimal(**money)
    stock_value = fields.Decimal(**money)
    by_day = fields.List(fields.Nested(DayOut))
    top_products = fields.List(fields.Nested(TopProductOut))
    low_stock = fields.List(fields.Nested(LowStockOut))


@blp.route("/summary")
@blp.arguments(ReportQuery, location="query")
@blp.response(200, SummaryOut)
@roles_required("admin")
def summary(args):
    days = args["days"]
    today = datetime.now(UTC).date()
    date_from = today - timedelta(days=days - 1)
    since = datetime.combine(date_from, datetime.min.time(), tzinfo=UTC)
    in_range = Sale.created_at >= since
    zero = Decimal("0")

    sales_total, sales_count = db.session.execute(
        db.select(db.func.coalesce(db.func.sum(Sale.total), 0), db.func.count(Sale.id)).where(
            in_range
        )
    ).one()
    profit = db.session.scalar(
        db.select(
            db.func.coalesce(
                db.func.sum((SaleItem.unit_price - Product.cost_price) * SaleItem.quantity), 0
            )
        )
        .join(Sale, SaleItem.sale_id == Sale.id)
        .join(Product, SaleItem.product_id == Product.id)
        .where(in_range)
    )
    purchases = db.session.scalar(
        db.select(db.func.coalesce(db.func.sum(Purchase.total), 0)).where(
            Purchase.status == "received", Purchase.updated_at >= since
        )
    )
    stock_value = db.session.scalar(
        db.select(db.func.coalesce(db.func.sum(Product.quantity * Product.cost_price), 0))
    )

    day = db.func.date(Sale.created_at)
    rows = db.session.execute(
        db.select(day, db.func.sum(Sale.total), db.func.count(Sale.id))
        .where(in_range)
        .group_by(day)
    ).all()
    totals = {row[0]: (row[1], row[2]) for row in rows}
    by_day = [
        {
            "day": date_from + timedelta(days=i),
            "total": totals.get(date_from + timedelta(days=i), (zero, 0))[0],
            "count": totals.get(date_from + timedelta(days=i), (zero, 0))[1],
        }
        for i in range(days)
    ]

    top = db.session.execute(
        db.select(
            Product.id,
            Product.name,
            db.func.sum(SaleItem.quantity),
            db.func.sum(SaleItem.unit_price * SaleItem.quantity).label("total"),
        )
        .join(Sale, SaleItem.sale_id == Sale.id)
        .join(Product, SaleItem.product_id == Product.id)
        .where(in_range)
        .group_by(Product.id, Product.name)
        .order_by(db.desc("total"))
        .limit(5)
    ).all()
    low = db.session.scalars(
        db.select(Product)
        .where(Product.quantity <= Product.reorder_level)
        .order_by(Product.quantity, Product.name)
        .limit(10)
    ).all()

    return {
        "days": days,
        "date_from": date_from,
        "date_to": today,
        "sales_total": sales_total,
        "sales_count": sales_count,
        "average_sale": (sales_total / sales_count) if sales_count else zero,
        "estimated_profit": profit,
        "purchases_received_total": purchases,
        "stock_value": stock_value,
        "by_day": by_day,
        "top_products": [
            {"product_id": r[0], "name": r[1], "quantity": r[2], "total": r[3]} for r in top
        ],
        "low_stock": low,
    }