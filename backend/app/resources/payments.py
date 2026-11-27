import hmac
import math
import uuid
from datetime import UTC, datetime, timedelta

from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import fields, validate

from app import mpesa
from app.audit import audit
from app.auth import is_role, roles_required
from app.crud import get_or_404
from app.extensions import db
from app.models import MpesaPayment
from app.notify import notify_roles
from app.resources.sales import SaleLineIn, SaleProblem, cart, check_cart, record_sale
from app.schemas import Schema
from app.tenancy import tenant

blp = Blueprint(
    "payments", __name__, url_prefix="/api/payments", description="M-Pesa payments at the till"
)

CHECK_AFTER = timedelta(seconds=20)
CHECK_EVERY = timedelta(seconds=10)
GIVE_UP_AFTER = timedelta(minutes=3)
OUTCOMES = {
    1: ("failed", "The customer's M-Pesa balance is too low."),
    1032: ("cancelled", "The customer cancelled the M-Pesa prompt."),
    1037: ("failed", "The customer's phone did not answer in time."),
    2001: ("failed", "The customer entered the wrong M-Pesa PIN."),
}


class StartIn(Schema):
    phone = fields.String(required=True, validate=validate.Length(min=9, max=16))
    items = fields.List(
        fields.Nested(SaleLineIn),
        required=True,
        validate=validate.Length(min=1, max=100, error="Add at least one product."),
    )
    idempotency_key = fields.String(required=True, validate=validate.Length(min=8, max=64))


class SimulateIn(Schema):
    outcome = fields.String(required=True, validate=validate.OneOf(("paid", "cancelled")))


class PaymentOut(Schema):
    id = fields.Integer()
    status = fields.String()
    phone = fields.String()
    amount = fields.Integer()
    simulated = fields.Boolean()
    receipt_number = fields.String(allow_none=True)
    result_desc = fields.String(allow_none=True)
    problem = fields.String(allow_none=True)
    sale_id = fields.Integer(allow_none=True)
    created_at = fields.DateTime()
    completed_at = fields.DateTime(allow_none=True)


class ConfigOut(Schema):
    mode = fields.String()
    enabled = fields.Boolean()


def now():
    return datetime.now(UTC)


def settle(payment, code, description, receipt=None):
    payment = db.session.scalar(
        db.select(MpesaPayment).where(MpesaPayment.id == payment.id).with_for_update()
    )
    if payment.status != "pending":
        return payment
    payment.result_code = code
    payment.completed_at = now()
    if code != 0:
        payment.status, payment.result_desc = OUTCOMES.get(code, ("failed", description))
        db.session.commit()
        return payment

    payment.status = "paid"
    payment.receipt_number = receipt
    payment.result_desc = "Paid"
    wanted = {int(pid): quantity for pid, quantity in payment.items.items()}
    try:
        with db.session.begin_nested():
            sale = record_sale(
                wanted, "mpesa", payment.attendant_id, payment.idempotency_key, receipt
            )
        payment.sale_id = sale.id
        audit(
            "paid",
            "sale",
            sale.id,
            f"{sale.reference} paid by M-Pesa {receipt} ({payment.amount})",
            user_id=payment.attendant_id,
        )
    except SaleProblem as problem:
        payment.problem = (
            f"M-Pesa {receipt} for {payment.amount} was received, but the sale could not be "
            f"completed: {problem.message} Sell it again or refund the customer."
        )
        notify_roles(("admin", "sales"), payment.problem, link="/sales")
    db.session.commit()
    return payment


def check_with_safaricom(payment):
    if payment.status != "pending" or payment.simulated:
        return payment
    age = now() - payment.created_at
    if age < CHECK_AFTER or (payment.checked_at and now() - payment.checked_at < CHECK_EVERY):
        return payment
    payment.checked_at = now()
    db.session.commit()
    try:
        answer = mpesa.stk_query(payment.checkout_request_id)
    except mpesa.MpesaError:
        if age > GIVE_UP_AFTER:
            return settle(payment, 1037, "No answer")
        return payment
    code = answer.get("ResultCode")
    if code is None:
        return payment
    code = int(code)
    if code == 0:
        return payment
    return settle(payment, code, answer.get("ResultDesc", "Failed"))


def visible(payment_id):
    payment = get_or_404(MpesaPayment, payment_id)
    if not is_role("admin") and payment.attendant_id != current_user.id:
        abort(404, message=f"Payment {payment_id} not found")
    return payment


@blp.route("/mpesa/config")
@blp.response(200, ConfigOut)
@roles_required()
def config():
    chosen = mpesa.mode()
    return {"mode": chosen, "enabled": chosen != "off"}


@blp.route("/mpesa", methods=["POST"])
@blp.arguments(StartIn)
@blp.response(201, PaymentOut)
@roles_required("sales")
def start(data):
    chosen = mpesa.mode()
    if chosen == "off":
        abort(409, message="M-Pesa prompts are not set up. Record the sale as M-Pesa by hand.")
    existing = db.session.scalar(
        db.select(MpesaPayment).where(MpesaPayment.idempotency_key == data["idempotency_key"])
    )
    if existing is not None:
        return existing
    phone = mpesa.normalise_phone(data["phone"])
    if phone is None:
        abort(422, message="Enter a Safaricom number like 0712 345 678.")
    wanted = cart(data["items"])
    try:
        _, total = check_cart(wanted)
    except SaleProblem as problem:
        db.session.rollback()
        abort(problem.status, message=problem.message)

    payment = MpesaPayment(
        attendant_id=current_user.id,
        phone=phone,
        amount=math.ceil(total),
        items={str(pid): quantity for pid, quantity in wanted.items()},
        idempotency_key=data["idempotency_key"],
        simulated=chosen == "simulate",
    )
    db.session.add(payment)
    db.session.flush()
    if payment.simulated:
        payment.checkout_request_id = f"SIM-{uuid.uuid4().hex}"
    else:
        try:
            checkout, merchant = mpesa.stk_push(
                phone, payment.amount, current_user.business.name, "StockPilot sale"
            )
        except mpesa.MpesaError as err:
            db.session.rollback()
            abort(502, message=str(err))
        payment.checkout_request_id, payment.merchant_request_id = checkout, merchant
    db.session.commit()
    return payment


@blp.route("/mpesa/<int:payment_id>")
@blp.response(200, PaymentOut)
@roles_required("admin", "sales")
def status(payment_id):
    return check_with_safaricom(visible(payment_id))


@blp.route("/mpesa/<int:payment_id>/simulate", methods=["POST"])
@blp.arguments(SimulateIn)
@blp.response(200, PaymentOut)
@roles_required("sales")
def simulate(data, payment_id):
    payment = visible(payment_id)
    if not payment.simulated:
        abort(409, message="Only test-mode payments can be simulated.")
    if data["outcome"] == "paid":
        return settle(payment, 0, "Paid", f"SIM{uuid.uuid4().hex[:7].upper()}")
    return settle(payment, 1032, "Cancelled")


@blp.route("/mpesa/callback/<string:token>", methods=["POST"])
@blp.response(200)
def callback(token):
    from flask import request

    if not hmac.compare_digest(token, mpesa.callback_token()):
        abort(404)
    body = (request.get_json(silent=True) or {}).get("Body", {}).get("stkCallback", {})
    checkout = body.get("CheckoutRequestID")
    payment = db.session.scalar(
        db.select(MpesaPayment).where(MpesaPayment.checkout_request_id == checkout)
    )
    if payment is not None:
        items = body.get("CallbackMetadata", {}).get("Item", [])
        values = {item.get("Name"): item.get("Value") for item in items}
        with tenant(payment.business_id):
            settle(
                payment,
                int(body.get("ResultCode", 1)),
                body.get("ResultDesc", ""),
                values.get("MpesaReceiptNumber"),
            )
    return {"ResultCode": 0, "ResultDesc": "Accepted"}
