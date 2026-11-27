from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import fields, validate

from app import mpesa
from app.auth import roles_required
from app.billing import PLANS, subscription
from app.crud import get_or_404
from app.extensions import db
from app.models import MpesaPayment
from app.resources.payments import PaymentOut, SimulateIn, simulated_outcome
from app.schemas import Schema
from app.settlement import follow_up, send_prompt

blp = Blueprint("billing", __name__, url_prefix="/api/billing", description="Subscription")


class SubscriptionOut(Schema):
    status = fields.String()
    required = fields.Boolean()
    trial_ends_on = fields.Date()
    paid_until = fields.Date(allow_none=True)
    ends_on = fields.Date()
    grace_until = fields.Date()
    days_left = fields.Integer()
    read_only = fields.Boolean()
    price = fields.Integer()
    plans = fields.List(fields.Integer())
    online_payment = fields.Boolean()
    payments = fields.List(fields.Nested(PaymentOut))


class PayIn(Schema):
    months = fields.Integer(required=True, validate=validate.OneOf(PLANS))
    phone = fields.String(required=True, validate=validate.Length(min=9, max=16))


def subscription_payment(payment_id):
    payment = get_or_404(MpesaPayment, payment_id)
    if payment.purpose != "subscription":
        abort(404, message=f"Payment {payment_id} not found")
    return payment


@blp.route("")
@blp.response(200, SubscriptionOut)
@roles_required("admin")
def overview():
    payments = db.session.scalars(
        db.select(MpesaPayment)
        .where(MpesaPayment.purpose == "subscription", MpesaPayment.status == "paid")
        .order_by(MpesaPayment.completed_at.desc())
        .limit(24)
    ).all()
    return {
        **subscription(current_user.business),
        "plans": PLANS,
        "online_payment": mpesa.platform_mode() != "off",
        "payments": payments,
    }


@blp.route("/pay", methods=["POST"])
@blp.arguments(PayIn)
@blp.response(201, PaymentOut)
@roles_required("admin")
def pay(data):
    account = mpesa.platform_account()
    if account.mode == "off":
        abort(409, message="Paying by M-Pesa is not available yet. Contact StockPilot to renew.")
    phone = mpesa.normalise_phone(data["phone"])
    if phone is None:
        abort(422, message="Enter a Safaricom number like 0712 345 678.")
    business = current_user.business
    payment = MpesaPayment(
        purpose="subscription",
        months=data["months"],
        attendant_id=current_user.id,
        phone=phone,
        amount=subscription(business)["price"] * data["months"],
        items={},
    )
    db.session.add(payment)
    db.session.flush()
    try:
        send_prompt(payment, account, f"SP{business.id}", "Subscription")
    except mpesa.MpesaError as err:
        db.session.rollback()
        abort(502, message=str(err))
    db.session.commit()
    return payment


@blp.route("/payments/<int:payment_id>")
@blp.response(200, PaymentOut)
@roles_required("admin")
def payment_status(payment_id):
    return follow_up(subscription_payment(payment_id))


@blp.route("/payments/<int:payment_id>/simulate", methods=["POST"])
@blp.arguments(SimulateIn)
@blp.response(200, PaymentOut)
@roles_required("admin")
def simulate(data, payment_id):
    return simulated_outcome(subscription_payment(payment_id), data["outcome"])
