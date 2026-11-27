from datetime import timedelta
from decimal import Decimal

from flask import Response
from flask_jwt_extended import current_user
from flask_smorest import Blueprint
from marshmallow import ValidationError, fields, validate, validates_schema

from app.auth import roles_required
from app.extensions import db
from app.loanreport import build_pdf, default_today, filename
from app.models import (
    Expense,
    GoodsReceipt,
    GoodsReceiptItem,
    Product,
    PurchaseItem,
    Sale,
    SaleItem,
    User,
)
from app.schemas import Schema
from app.shoptime import range_bounds, shop_day, shop_today

blp = Blueprint("reports", __name__, url_prefix="/api/reports", description="Reports (Admin)")

money = {"places": 2, "as_string": True}
MAX_DAYS = 366


class ReportQuery(Schema):
    days = fields.Integer(load_default=None, validate=validate.Range(min=1, max=365))
    date_from = fields.Date(load_default=None)
    date_to = fields.Date(load_default=None)

    @validates_schema
    def range_ok(self, data, **kwargs):
        if bool(data.get("date_from")) != bool(data.get("date_to")):
            raise ValidationError("Give both date_from and date_to.", "date_to")
        if data.get("date_from") and data["date_to"] < data["date_from"]:
            raise ValidationError("The end date is before the start date.", "date_to")
        if data.get("date_from") and (data["date_to"] - data["date_from"]).days >= MAX_DAYS:
            raise ValidationError("Choose a range of at most one year.", "date_to")


class DayOut(Schema):
    day = fields.Date()
    total = fields.Decimal(**money)
    count = fields.Integer()
    profit = fields.Decimal(**money)


class TopProductOut(Schema):
    product_id = fields.Integer()
    name = fields.String()
    sku = fields.String()
    quantity = fields.Integer()
    total = fields.Decimal(**money)
    profit = fields.Decimal(**money)


class LowStockOut(Schema):
    id = fields.Integer()
    sku = fields.String()
    name = fields.String()
    quantity = fields.Integer()
    reorder_level = fields.Integer()


class BreakdownOut(Schema):
    key = fields.String()
    label = fields.String()
    total = fields.Decimal(**money)
    count = fields.Integer()


class SummaryOut(Schema):
    days = fields.Integer()
    date_from = fields.Date()
    date_to = fields.Date()
    sales_total = fields.Decimal(**money)
    sales_count = fields.Integer()
    average_sale = fields.Decimal(**money)
    vat_total = fields.Decimal(**money)
    cost_of_sales = fields.Decimal(**money)
    gross_profit = fields.Decimal(**money)
    estimated_profit = fields.Decimal(**money)
    expenses_total = fields.Decimal(**money)
    net_profit = fields.Decimal(**money)
    voided_count = fields.Integer()
    purchases_received_total = fields.Decimal(**money)
    stock_value = fields.Decimal(**money)
    by_day = fields.List(fields.Nested(DayOut))
    by_payment = fields.List(fields.Nested(BreakdownOut))
    by_attendant = fields.List(fields.Nested(BreakdownOut))
    expenses_by_category = fields.List(fields.Nested(BreakdownOut))
    top_products = fields.List(fields.Nested(TopProductOut))
    low_stock = fields.List(fields.Nested(LowStockOut))


PAYMENT_LABELS = {"cash": "Cash", "mpesa": "M-Pesa", "card": "Card"}


def resolve_range(args):
    if args["date_from"]:
        return args["date_from"], args["date_to"]
    today = shop_today()
    days = args["days"] or 7
    return today - timedelta(days=days - 1), today


@blp.route("/summary")
@blp.arguments(ReportQuery, location="query")
@blp.response(200, SummaryOut)
@roles_required("admin")
def summary(args):
    date_from, date_to = resolve_range(args)
    days = (date_to - date_from).days + 1
    start, end = range_bounds(date_from, date_to)
    zero = Decimal("0")
    sold = (Sale.created_at >= start) & (Sale.created_at < end) & (Sale.status == "completed")
    line_profit = (SaleItem.unit_price - SaleItem.unit_cost) * SaleItem.quantity

    sales_total, sales_count, vat_total = db.session.execute(
        db.select(
            db.func.coalesce(db.func.sum(Sale.total), 0),
            db.func.count(Sale.id),
            db.func.coalesce(db.func.sum(Sale.vat_amount), 0),
        ).where(sold)
    ).one()
    cost_of_sales, gross = db.session.execute(
        db.select(
            db.func.coalesce(db.func.sum(SaleItem.unit_cost * SaleItem.quantity), 0),
            db.func.coalesce(db.func.sum(line_profit), 0),
        )
        .join(Sale, SaleItem.sale_id == Sale.id)
        .where(sold)
    ).one()
    voided = db.session.scalar(
        db.select(db.func.count(Sale.id)).where(
            Sale.created_at >= start, Sale.created_at < end, Sale.status == "voided"
        )
    )
    expenses_total = db.session.scalar(
        db.select(db.func.coalesce(db.func.sum(Expense.amount), 0)).where(
            Expense.spent_on >= date_from, Expense.spent_on <= date_to
        )
    )
    purchases = db.session.scalar(
        db.select(
            db.func.coalesce(db.func.sum(GoodsReceiptItem.quantity * PurchaseItem.unit_cost), 0)
        )
        .join(GoodsReceipt, GoodsReceiptItem.receipt_id == GoodsReceipt.id)
        .join(PurchaseItem, GoodsReceiptItem.purchase_item_id == PurchaseItem.id)
        .where(GoodsReceipt.created_at >= start, GoodsReceipt.created_at < end)
    )
    stock_value = db.session.scalar(
        db.select(db.func.coalesce(db.func.sum(Product.quantity * Product.cost_price), 0))
    )

    day = shop_day(Sale.created_at)
    totals = {
        row[0]: (row[1], row[2])
        for row in db.session.execute(
            db.select(day, db.func.sum(Sale.total), db.func.count(Sale.id))
            .where(sold)
            .group_by(day)
        )
    }
    profits = dict(
        db.session.execute(
            db.select(day, db.func.sum(line_profit))
            .join(Sale, SaleItem.sale_id == Sale.id)
            .where(sold)
            .group_by(day)
        ).all()
    )
    by_day = []
    for i in range(days):
        d = date_from + timedelta(days=i)
        total, count = totals.get(d, (zero, 0))
        by_day.append({"day": d, "total": total, "count": count, "profit": profits.get(d, zero)})

    by_payment = [
        {"key": method, "label": PAYMENT_LABELS.get(method, method), "total": total, "count": n}
        for method, total, n in db.session.execute(
            db.select(Sale.payment_method, db.func.sum(Sale.total), db.func.count(Sale.id))
            .where(sold)
            .group_by(Sale.payment_method)
            .order_by(db.func.sum(Sale.total).desc())
        )
    ]
    by_attendant = [
        {"key": str(uid), "label": name, "total": total, "count": n}
        for uid, name, total, n in db.session.execute(
            db.select(User.id, User.full_name, db.func.sum(Sale.total), db.func.count(Sale.id))
            .join(User, User.id == Sale.attendant_id)
            .where(sold)
            .group_by(User.id, User.full_name)
            .order_by(db.func.sum(Sale.total).desc())
        )
    ]
    expenses_by_category = [
        {"key": category, "label": category, "total": total, "count": n}
        for category, total, n in db.session.execute(
            db.select(Expense.category, db.func.sum(Expense.amount), db.func.count(Expense.id))
            .where(Expense.spent_on >= date_from, Expense.spent_on <= date_to)
            .group_by(Expense.category)
            .order_by(db.func.sum(Expense.amount).desc())
        )
    ]
    top = db.session.execute(
        db.select(
            Product.id,
            Product.name,
            Product.sku,
            db.func.sum(SaleItem.quantity),
            db.func.sum(SaleItem.unit_price * SaleItem.quantity).label("total"),
            db.func.sum(line_profit),
        )
        .join(Sale, SaleItem.sale_id == Sale.id)
        .join(Product, SaleItem.product_id == Product.id)
        .where(sold)
        .group_by(Product.id, Product.name, Product.sku)
        .order_by(db.desc("total"))
        .limit(10)
    ).all()
    low = db.session.scalars(
        db.select(Product)
        .where(Product.quantity <= Product.reorder_level, Product.is_active.is_(True))
        .order_by(Product.quantity, Product.name)
        .limit(20)
    ).all()

    return {
        "days": days,
        "date_from": date_from,
        "date_to": date_to,
        "sales_total": sales_total,
        "sales_count": sales_count,
        "average_sale": (sales_total / sales_count) if sales_count else zero,
        "vat_total": vat_total,
        "cost_of_sales": cost_of_sales,
        "gross_profit": gross,
        "estimated_profit": gross,
        "expenses_total": expenses_total,
        "net_profit": gross - expenses_total,
        "voided_count": voided,
        "purchases_received_total": purchases,
        "stock_value": stock_value,
        "by_day": by_day,
        "by_payment": by_payment,
        "by_attendant": by_attendant,
        "expenses_by_category": expenses_by_category,
        "top_products": [
            {
                "product_id": r[0],
                "name": r[1],
                "sku": r[2],
                "quantity": r[3],
                "total": r[4],
                "profit": r[5],
            }
            for r in top
        ],
        "low_stock": low,
    }


class LoanReportQuery(Schema):
    months = fields.Integer(load_default=6, validate=validate.OneOf((3, 6, 12)))


@blp.route("/performance.pdf")
@blp.arguments(LoanReportQuery, location="query")
@roles_required("admin")
def performance_pdf(args):
    business = current_user.business
    today = default_today(business)
    return Response(
        build_pdf(business, args["months"], today),
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename(business, today)}"'},
    )
