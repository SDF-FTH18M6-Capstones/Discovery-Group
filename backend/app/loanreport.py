import io
from collections import defaultdict
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.extensions import db
from app.models import Expense, MoneyTransaction, Product, Sale
from app.models.money import TRANSFERS

GREEN = colors.HexColor("#0f6e4f")
INK = colors.HexColor("#1d2b26")
MUTED = colors.HexColor("#5f6f69")
LINE = colors.HexColor("#d9e2de")
ZERO = Decimal("0")


def month_starts(today, months):
    first = today.replace(day=1)
    starts = []
    for _ in range(months):
        first = (first - timedelta(days=1)).replace(day=1)
        starts.append(first)
    return list(reversed(starts))


def next_month(day):
    return (day.replace(day=28) + timedelta(days=4)).replace(day=1)


def figures(business, months, today):
    zone = ZoneInfo(business.timezone)
    starts = month_starts(today, months)
    since = datetime.combine(starts[0], time.min, zone).astimezone(UTC)
    until = datetime.combine(next_month(starts[-1]), time.min, zone).astimezone(UTC)

    def month_of(moment):
        return moment.astimezone(zone).date().replace(day=1)

    rows = {start: defaultdict(lambda: ZERO) for start in starts}
    trading_days = set()
    for created, total in db.session.execute(
        db.select(Sale.created_at, Sale.total).where(
            Sale.status == "completed", Sale.created_at >= since, Sale.created_at < until
        )
    ):
        rows[month_of(created)]["sales"] += total
        trading_days.add(created.astimezone(zone).date())

    customers = defaultdict(int)
    balances = {}
    borrowed = repaid = ZERO
    counted = 0
    for moment, direction, amount, category, sale_id, balance, who, phone in db.session.execute(
        db.select(
            MoneyTransaction.occurred_at,
            MoneyTransaction.direction,
            MoneyTransaction.amount,
            MoneyTransaction.category,
            MoneyTransaction.sale_id,
            MoneyTransaction.balance,
            MoneyTransaction.counterparty,
            MoneyTransaction.phone,
        )
        .where(MoneyTransaction.occurred_at >= since, MoneyTransaction.occurred_at < until)
        .order_by(MoneyTransaction.occurred_at, MoneyTransaction.id)
    ):
        counted += 1
        row = rows[month_of(moment)]
        if balance is not None:
            balances[month_of(moment)] = balance
        if category in TRANSFERS:
            continue
        if direction == "in" and category == "sales":
            customers[phone or who] += 1
            if sale_id is None:
                row["sales"] += amount
                trading_days.add(moment.astimezone(zone).date())
        elif direction == "in":
            row["other_in"] += amount
            if category == "loan":
                borrowed += amount
        else:
            row["spending"] += amount
            if category == "loan_repayment":
                repaid += amount

    for spent_on, amount in db.session.execute(
        db.select(Expense.spent_on, Expense.amount).where(
            Expense.spent_on >= starts[0], Expense.spent_on < next_month(starts[-1])
        )
    ):
        rows[spent_on.replace(day=1)]["spending"] += amount

    table = []
    for start in starts:
        row = rows[start]
        net = row["sales"] + row["other_in"] - row["spending"]
        table.append(
            {
                "month": start,
                "sales": row["sales"],
                "other_in": row["other_in"],
                "spending": row["spending"],
                "net": net,
                "balance": balances.get(start),
            }
        )

    sales = [row["sales"] for row in table]
    half = len(table) // 2
    early = sum(sales[:half]) / half if half else ZERO
    late = sum(sales[-half:]) / half if half else ZERO
    stock_value = db.session.scalar(
        db.select(db.func.coalesce(db.func.sum(Product.quantity * Product.cost_price), 0)).where(
            Product.is_active, Product.quantity > 0
        )
    )
    days = (next_month(starts[-1]) - starts[0]).days
    return {
        "starts": starts,
        "rows": table,
        "average_sales": sum(sales) / len(sales),
        "best": max(table, key=lambda r: r["sales"]),
        "lowest": min(table, key=lambda r: r["sales"]),
        "positive_months": sum(1 for row in table if row["net"] > 0),
        "growth": round((late - early) / early * 100) if early else None,
        "trading_days": len(trading_days),
        "days": days,
        "customers": len(customers),
        "regulars": sum(1 for visits in customers.values() if visits >= 3),
        "borrowed": borrowed,
        "repaid": repaid,
        "stock_value": Decimal(stock_value),
        "mpesa_rows": counted,
    }


def build_pdf(business, months, today=None):
    today = today or datetime.now(ZoneInfo(business.timezone)).date()
    data = figures(business, months, today)
    currency = business.currency

    def amount(value):
        return "-" if value is None else f"{value:,.0f}"

    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "body", parent=styles["BodyText"], fontSize=9.5, leading=13, textColor=INK
    )
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=11, textColor=MUTED)
    heading = ParagraphStyle(
        "heading", parent=styles["Heading2"], fontSize=12.5, textColor=GREEN, spaceBefore=10
    )
    title = ParagraphStyle(
        "title", parent=styles["Title"], fontSize=20, leading=24, alignment=0, textColor=INK
    )

    period = f"{data['starts'][0]:%B %Y} to {data['starts'][-1]:%B %Y}"
    details = (business.address, business.phone, business.email)
    contact = " · ".join(part for part in details if part)
    story = [
        Paragraph(business.name, title),
        Paragraph(contact or "&nbsp;", small),
        Spacer(1, 6),
        Paragraph(f"<b>Business performance report</b>, {period}", body),
        Paragraph(f"Prepared on {today:%d %B %Y}. Amounts in {currency}.", small),
        Spacer(1, 8),
    ]

    growth = data["growth"]
    growth_text = "-" if growth is None else f"{growth:+d}%"
    key = [
        ["Average monthly sales", "Best month", "Months with more in than out"],
        [
            amount(data["average_sales"]),
            f"{data['best']['month']:%b %Y}: {amount(data['best']['sales'])}",
            f"{data['positive_months']} of {len(data['rows'])}",
        ],
        ["Sales trend (second half vs first)", "Days with sales", "Paying customers (regulars)"],
        [
            growth_text,
            f"{data['trading_days']} of {data['days']}",
            f"{data['customers']} ({data['regulars']})",
        ],
    ]
    grid = Table(key, colWidths=[60 * mm] * 3)
    grid.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
                ("TEXTCOLOR", (0, 2), (-1, 2), MUTED),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (-1, 1), 12),
                ("FONTSIZE", (0, 3), (-1, 3), 12),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f8f6")),
            ]
        )
    )
    story += [grid, Paragraph("Monthly sales", heading)]

    chart = Drawing(170 * mm, 55 * mm)
    bars = VerticalBarChart()
    bars.x, bars.y, bars.width, bars.height = 12 * mm, 8 * mm, 155 * mm, 42 * mm
    bars.data = [[float(row["sales"]) for row in data["rows"]]]
    bars.categoryAxis.categoryNames = [f"{row['month']:%b %y}" for row in data["rows"]]
    bars.categoryAxis.labels.fontSize = 7
    bars.valueAxis.labels.fontSize = 7
    bars.valueAxis.valueMin = 0
    bars.valueAxis.labelTextFormat = lambda value: f"{value / 1000:,.0f}k"
    bars.bars[0].fillColor = GREEN
    bars.bars[0].strokeColor = None
    bars.valueAxis.strokeColor = LINE
    bars.categoryAxis.strokeColor = LINE
    chart.add(bars)
    story.append(chart)

    story.append(Paragraph("Month by month", heading))
    header = ["Month", "Sales", "Other money in", "Spending", "In minus out", "M-Pesa balance"]
    lines = [header] + [
        [
            f"{row['month']:%B %Y}",
            amount(row["sales"]),
            amount(row["other_in"]),
            amount(row["spending"]),
            amount(row["net"]),
            amount(row["balance"]),
        ]
        for row in data["rows"]
    ]
    sold, other, spent = (
        sum((row[key] for row in data["rows"]), ZERO) for key in ("sales", "other_in", "spending")
    )
    lines.append(
        ["Total", amount(sold), amount(other), amount(spent), amount(sold + other - spent), ""]
    )
    monthly = Table(lines, colWidths=[34 * mm, 27 * mm, 29 * mm, 27 * mm, 27 * mm, 30 * mm])
    monthly.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 0), (-1, 0), GREEN),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("LINEBELOW", (0, 1), (-1, -2), 0.4, LINE),
                ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(monthly)

    story += [
        Paragraph("Borrowing and assets", heading),
        Paragraph(
            "Loans and overdrafts received in the period: "
            f"<b>{currency} {amount(data['borrowed'])}</b>. "
            f"Repaid in the period: <b>{currency} {amount(data['repaid'])}</b>. "
            f"Stock on hand at cost today: <b>{currency} {amount(data['stock_value'])}</b>.",
            body,
        ),
        Paragraph("How these figures were prepared", heading),
        Paragraph(
            "Sales are completed sales recorded at the till plus M-Pesa payments from customers "
            "that were not already rung up. Other money in includes loans. Spending is M-Pesa "
            "money paid out plus expenses recorded in StockPilot. Money the owner moved in or out, "
            "and savings, are left out. "
            f"{data['mpesa_rows']} M-Pesa transactions were imported for this period. "
            "The business keeps these records itself; they have not been audited.",
            small,
        ),
    ]

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 10 * mm, f"{business.name} · prepared with StockPilot")
        canvas.drawRightString(192 * mm, 10 * mm, f"Page {document.page}")
        canvas.restoreState()

    out = io.BytesIO()
    document = SimpleDocTemplate(
        out,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=f"{business.name} performance report",
        author=business.name,
    )
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()


def filename(business, today):
    safe = "".join(c if c.isalnum() else "-" for c in business.name).strip("-").lower()
    return f"{safe}-performance-{today:%Y-%m}.pdf"


def default_today(business):
    return datetime.now(ZoneInfo(business.timezone)).date()
