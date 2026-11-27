import math
from datetime import UTC, datetime
from functools import wraps

from flask import current_app
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_smorest import Blueprint, abort
from marshmallow import fields, validate

from app import mpesa
from app.audit import audit
from app.billing import extend, monthly_price, set_monthly_price, subscription
from app.crud import PageQuery
from app.extensions import db
from app.models import Business, MpesaPayment, Sale, User
from app.notify import notify_roles
from app.schemas import Schema
from app.tenancy import tenant

blp = Blueprint(
    "platform", __name__, url_prefix="/api/platform", description="StockPilot owners only"
)

STATUSES = ("trial", "active", "grace", "expired", "suspended")


def is_platform_owner(user):
    return user.email.lower() in current_app.config["PLATFORM_OWNERS"]


def owners_only(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        if not is_platform_owner(current_user):
            abort(404)
        return view(*args, **kwargs)

    return wrapper


def everywhere(statement):
    return statement.execution_options(all_businesses=True)


def status_of(business):
    return "suspended" if not business.is_active else subscription(business)["status"]


class BusinessRow(Schema):
    id = fields.Integer()
    name = fields.String()
    created_at = fields.DateTime()
    owner_email = fields.String(allow_none=True)
    staff = fields.Integer()
    last_sale_at = fields.DateTime(allow_none=True)
    status = fields.String()
    ends_on = fields.Date()
    paid_until = fields.Date(allow_none=True)
    is_active = fields.Boolean()


class BusinessPage(Schema):
    results = fields.List(fields.Nested(BusinessRow))
    count = fields.Integer()
    page = fields.Integer()
    per_page = fields.Integer()
    pages = fields.Integer()


class BusinessQuery(PageQuery):
    search = fields.String(load_default=None)
    status = fields.String(load_default=None, validate=validate.OneOf(STATUSES))


class PaymentRow(Schema):
    id = fields.Integer()
    business_id = fields.Integer()
    business_name = fields.String()
    months = fields.Integer()
    amount = fields.Integer()
    phone = fields.String()
    receipt_number = fields.String()
    simulated = fields.Boolean()
    completed_at = fields.DateTime()


class PaymentPage(Schema):
    results = fields.List(fields.Nested(PaymentRow))
    count = fields.Integer()
    page = fields.Integer()
    per_page = fields.Integer()
    pages = fields.Integer()


class Overview(Schema):
    businesses = fields.Integer()
    by_status = fields.Dict(keys=fields.String(), values=fields.Integer())
    revenue_this_month = fields.Integer()
    revenue_total = fields.Integer()
    price = fields.Integer()
    paybill_mode = fields.String()
    paybill_connected = fields.Boolean()
    subscriptions_required = fields.Boolean()


class PriceIn(Schema):
    price = fields.Integer(required=True, validate=validate.Range(min=1, max=1_000_000))


class ExtendIn(Schema):
    months = fields.Integer(required=True, validate=validate.Range(min=1, max=24))
    note = fields.String(
        required=True,
        validate=validate.Length(min=3, max=200, error="Say why (3 to 200 characters)."),
    )


class SuspendIn(Schema):
    reason = fields.String(
        required=True,
        validate=validate.Length(min=3, max=200, error="Say why (3 to 200 characters)."),
    )


def page_info(count, args):
    return {
        "count": count,
        "page": args["page"],
        "per_page": args["per_page"],
        "pages": math.ceil(count / args["per_page"]) if count else 0,
    }


def paid_total(since=None):
    query = db.select(db.func.coalesce(db.func.sum(MpesaPayment.amount), 0)).where(
        MpesaPayment.purpose == "subscription",
        MpesaPayment.status == "paid",
        MpesaPayment.simulated.is_(False),
    )
    if since is not None:
        query = query.where(MpesaPayment.completed_at >= since)
    return db.session.scalar(everywhere(query))


def row(business, owners, staff, last_sales):
    plan = subscription(business)
    return {
        "id": business.id,
        "name": business.name,
        "created_at": business.created_at,
        "owner_email": owners.get(business.id),
        "staff": staff.get(business.id, 0),
        "last_sale_at": last_sales.get(business.id),
        "status": status_of(business),
        "ends_on": plan["ends_on"],
        "paid_until": business.paid_until,
        "is_active": business.is_active,
    }


def find_business(business_id):
    business = db.session.get(Business, business_id)
    if business is None:
        abort(404, message=f"Business {business_id} not found")
    return business


def tell_admins(business, message, subject):
    with tenant(business.id):
        notify_roles(("admin",), message, link="/billing", email_subject=subject)


def summary():
    businesses = db.session.scalars(db.select(Business)).all()
    by_status = dict.fromkeys(STATUSES, 0)
    for business in businesses:
        by_status[status_of(business)] += 1
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    account = mpesa.platform_account()
    return {
        "businesses": len(businesses),
        "by_status": by_status,
        "revenue_this_month": paid_total(month_start),
        "revenue_total": paid_total(),
        "price": monthly_price(),
        "paybill_mode": account.mode,
        "paybill_connected": account.online
        and bool(account.consumer_key and account.consumer_secret),
        "subscriptions_required": current_app.config["SUBSCRIPTIONS_REQUIRED"],
    }


@blp.route("/overview")
@blp.response(200, Overview)
@owners_only
def overview():
    return summary()


@blp.route("/businesses")
@blp.arguments(BusinessQuery, location="query")
@blp.response(200, BusinessPage)
@owners_only
def businesses(args):
    query = db.select(Business).order_by(Business.created_at.desc(), Business.id.desc())
    if args["search"]:
        query = query.where(Business.name.ilike(f"%{args['search']}%"))
    everyone = db.session.scalars(query).all()
    if args["status"]:
        everyone = [b for b in everyone if status_of(b) == args["status"]]
    total = len(everyone)
    start = (args["page"] - 1) * args["per_page"]
    shown = everyone[start : start + args["per_page"]]
    ids = [b.id for b in shown]

    owners = {}
    for business_id, email in db.session.execute(
        everywhere(
            db.select(User.business_id, User.email)
            .where(User.business_id.in_(ids), User.role == "admin")
            .order_by(User.id)
        )
    ):
        owners.setdefault(business_id, email)
    staff = dict(
        db.session.execute(
            everywhere(
                db.select(User.business_id, db.func.count())
                .where(User.business_id.in_(ids), User.is_active.is_(True))
                .group_by(User.business_id)
            )
        ).all()
    )
    last_sales = dict(
        db.session.execute(
            everywhere(
                db.select(Sale.business_id, db.func.max(Sale.created_at))
                .where(Sale.business_id.in_(ids))
                .group_by(Sale.business_id)
            )
        ).all()
    )
    return {
        "results": [row(b, owners, staff, last_sales) for b in shown],
        **page_info(total, args),
    }


@blp.route("/payments")
@blp.arguments(PageQuery, location="query")
@blp.response(200, PaymentPage)
@owners_only
def payments(args):
    query = everywhere(
        db.select(MpesaPayment, Business.name)
        .join(Business, Business.id == MpesaPayment.business_id)
        .where(MpesaPayment.purpose == "subscription", MpesaPayment.status == "paid")
        .order_by(MpesaPayment.completed_at.desc())
    )
    total = db.session.scalar(
        everywhere(
            db.select(db.func.count()).where(
                MpesaPayment.purpose == "subscription", MpesaPayment.status == "paid"
            )
        )
    )
    rows = db.session.execute(
        query.limit(args["per_page"]).offset((args["page"] - 1) * args["per_page"])
    ).all()
    return {
        "results": [
            {
                "id": payment.id,
                "business_id": payment.business_id,
                "business_name": name,
                "months": payment.months,
                "amount": payment.amount,
                "phone": payment.phone,
                "receipt_number": payment.receipt_number,
                "simulated": payment.simulated,
                "completed_at": payment.completed_at,
            }
            for payment, name in rows
        ],
        **page_info(total, args),
    }


@blp.route("/price", methods=["PUT"])
@blp.arguments(PriceIn)
@blp.response(200, Overview)
@owners_only
def change_price(data):
    set_monthly_price(data["price"])
    db.session.commit()
    return summary()


@blp.route("/businesses/<int:business_id>/extend", methods=["POST"])
@blp.arguments(ExtendIn)
@blp.response(200, BusinessRow)
@owners_only
def extend_business(data, business_id):
    business = find_business(business_id)
    until = extend(business, data["months"])
    plural = "s" if data["months"] != 1 else ""
    with tenant(business.id):
        audit(
            "extended",
            "business",
            business.id,
            f"StockPilot added {data['months']} month{plural}: {data['note']}",
            user_id=None,
        )
    tell_admins(
        business,
        f"StockPilot added {data['months']} month{plural} to {business.name}'s subscription. "
        f"It is now paid until {until:%d %B %Y}.",
        "Your StockPilot subscription was extended",
    )
    db.session.commit()
    return row(business, {}, {}, {})


@blp.route("/businesses/<int:business_id>/suspend", methods=["POST"])
@blp.arguments(SuspendIn)
@blp.response(200, BusinessRow)
@owners_only
def suspend(data, business_id):
    business = find_business(business_id)
    if business.id == current_user.business_id:
        abort(409, message="You cannot suspend your own business.")
    if not business.is_active:
        abort(409, message=f"{business.name} is already suspended.")
    tell_admins(
        business,
        f"StockPilot has suspended {business.name}: {data['reason']}",
        "Your StockPilot account is suspended",
    )
    business.is_active = False
    with tenant(business.id):
        audit("suspended", "business", business.id, f"Suspended: {data['reason']}", user_id=None)
    db.session.commit()
    return row(business, {}, {}, {})


@blp.route("/businesses/<int:business_id>/reactivate", methods=["POST"])
@blp.response(200, BusinessRow)
@owners_only
def reactivate(business_id):
    business = find_business(business_id)
    if business.is_active:
        abort(409, message=f"{business.name} is already active.")
    business.is_active = True
    with tenant(business.id):
        audit("reactivated", "business", business.id, "Reactivated by StockPilot", user_id=None)
    tell_admins(
        business,
        f"{business.name} is active again. Welcome back!",
        "Your StockPilot account is active again",
    )
    db.session.commit()
    return row(business, {}, {}, {})
