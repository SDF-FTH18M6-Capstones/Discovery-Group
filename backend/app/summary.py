from decimal import Decimal

from flask import current_app

from app.extensions import db
from app.insights import cash_outlook, sales_outlook, stock_outlook
from app.mail import queue_email
from app.models import Business, Product, Purchase, Sale, SaleItem, User
from app.shoptime import day_bounds, shop_today
from app.tenancy import tenant
from app.whatsapp import queue_alert

METHOD_NAMES = {"cash": "Cash", "mpesa": "M-Pesa", "card": "Card"}


def money(currency, amount):
    return f"{currency} {amount:,.2f}"


def looking_ahead(business):
    currency = business.currency
    sales = sales_outlook(business)
    lines = []
    if sales["ready"]:
        week = sum(Decimal(str(day["expected"])) for day in sales["forecast"][:7])
        lines.append(f"Expected sales over the next 7 days: about {money(currency, week)}")
    running_out = stock_outlook()["running_out"][:5]
    if running_out:
        lines.append("Running out soon:")
        for item in running_out:
            days = f"{item['days_left']} day{'s' if item['days_left'] != 1 else ''}"
            order = item["suggested_order"]
            lines.append(f"  {item['name']}: about {days} left, order about {order}")
    warning = cash_warning(business, sales)
    if warning:
        lines.append(f"Cash: {warning}")
    return lines


def cash_warning(business, sales=None):
    cash = cash_outlook(business, sales or sales_outlook(business))
    if not cash["ready"] or cash["expected_net"] >= 0:
        return None
    short = money(business.currency, abs(Decimal(str(cash["expected_net"]))))
    return f"more is likely to go out than come in over the next 30 days, by about {short}."


def summary_for(business):
    today = shop_today()
    start, end = day_bounds(today)
    sales = db.session.scalars(
        db.select(Sale).where(Sale.created_at >= start, Sale.created_at < end)
    ).all()
    kept = [sale for sale in sales if sale.status == "completed"]
    voided = len(sales) - len(kept)
    total = sum((sale.total for sale in kept), Decimal("0"))
    by_method = {}
    for sale in kept:
        by_method[sale.payment_method] = by_method.get(sale.payment_method, 0) + sale.total
    best = db.session.execute(
        db.select(Product.name, db.func.sum(SaleItem.quantity))
        .join(SaleItem.product)
        .join(SaleItem.sale)
        .where(Sale.status == "completed", Sale.created_at >= start, Sale.created_at < end)
        .group_by(Product.name)
        .order_by(db.func.sum(SaleItem.quantity).desc(), Product.name)
        .limit(3)
    ).all()
    low = db.session.scalars(
        db.select(Product.name)
        .where(Product.is_active.is_(True), Product.quantity <= Product.reorder_level)
        .order_by(Product.quantity, Product.name)
    ).all()
    drafts = db.session.scalar(
        db.select(db.func.count()).select_from(Purchase).where(Purchase.status == "draft")
    )
    waiting = db.session.scalar(
        db.select(db.func.count()).select_from(User).where(User.approved_at.is_(None))
    )

    currency = business.currency
    lines = [f"Here is how {business.name} did today, {today:%A %d %B}.", ""]
    if kept:
        lines.append(f"Sales: {len(kept)} receipts, {money(currency, total)}")
        for method, amount in sorted(by_method.items()):
            lines.append(f"  {METHOD_NAMES.get(method, method)}: {money(currency, amount)}")
        if best:
            sold = ", ".join(f"{name} ({quantity})" for name, quantity in best)
            lines.append(f"Best sellers: {sold}")
    else:
        lines.append("No sales were recorded today.")
    if voided:
        lines.append(f"Voided: {voided} receipt{'s' if voided != 1 else ''}")
    lines.append("")
    if low:
        shown = ", ".join(low[:5]) + (f" and {len(low) - 5} more" if len(low) > 5 else "")
        lines.append(f"Low on stock: {shown}")
    if drafts:
        lines.append(f"Draft orders waiting for Procurement to confirm: {drafts}")
    if waiting:
        lines.append(f"New staff waiting for your approval: {waiting}")
    if not (low or drafts or waiting):
        lines.append("Nothing is waiting on anyone.")
    ahead = looking_ahead(business)
    if ahead:
        lines += ["", "Looking ahead", *ahead]
    lines += ["", f"Open StockPilot: {current_app.config['FRONTEND_URL']}/", "", "- StockPilot"]
    subject = f"{business.name} today: {money(currency, total)} from {len(kept)} sales"
    return subject, "\n".join(lines)


def send_daily_summaries():
    sent = 0
    ids = db.session.scalars(
        db.select(Business.id).where(
            Business.is_active.is_(True),
            db.or_(Business.daily_summary.is_(True), Business.whatsapp_alerts.is_(True)),
        )
    ).all()
    for business_id in ids:
        with tenant(business_id):
            business = db.session.get(Business, business_id)
            if business.summary_sent_on == shop_today():
                continue
            admins = db.session.scalars(
                db.select(User.email).where(
                    User.role == "admin",
                    User.is_active.is_(True),
                    User.approved_at.is_not(None),
                )
            ).all()
            if business.daily_summary:
                subject, body = summary_for(business)
                for email in admins:
                    queue_email(email, subject, body)
                sent += 1
            warning = cash_warning(business)
            if warning:
                queue_alert(business, f"Cash: {warning}")
            business.summary_sent_on = shop_today()
            db.session.commit()
    return sent
