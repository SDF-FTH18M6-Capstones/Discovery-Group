import hmac
import math

from flask import request
from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import fields, validate

from app import mpesa
from app.auth import is_role, roles_required
from app.crud import get_or_404
from app.extensions import db
from app.models import MpesaPayment
from app.resources.sales import SaleLineIn, SaleProblem, cart, check_cart
from app.schemas import Schema
from app.settlement import follow_up, send_prompt, settle
from app.tenancy import tenant

blp = Blueprint(
    "payments", __name__, url_prefix="/api/payments", description="M-Pesa payments at the till"
)


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
    purpose = fields.String()
    status = fields.String()
    phone = fields.String()
    amount = fields.Integer()
    months = fields.Integer(allow_none=True)
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


def sale_payment(payment_id):
    payment = get_or_404(MpesaPayment, payment_id)
    if payment.purpose != "sale":
        abort(404, message=f"Payment {payment_id} not found")
    if not is_role("admin") and payment.attendant_id != current_user.id:
        abort(404, message=f"Payment {payment_id} not found")
    return payment


def simulated_outcome(payment, outcome):
    if not payment.simulated:
        abort(409, message="Only test-mode payments can be simulated.")
    if outcome == "paid":
        return settle(payment, 0, "Paid", f"SIM{payment.id:07d}")
    return settle(payment, 1032, "Cancelled")


@blp.route("/mpesa/config")
@blp.response(200, ConfigOut)
@roles_required()
def config():
    mode = mpesa.business_account(current_user.business).mode
    return {"mode": mode, "enabled": mode != "off"}


@blp.route("/mpesa", methods=["POST"])
@blp.arguments(StartIn)
@blp.response(201, PaymentOut)
@roles_required("sales")
def start(data):
    business = current_user.business
    account = mpesa.business_account(business)
    if account.mode == "off":
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
    )
    db.session.add(payment)
    db.session.flush()
    try:
        send_prompt(payment, account, business.name, "StockPilot sale")
    except mpesa.MpesaError as err:
        db.session.rollback()
        abort(502, message=str(err))
    db.session.commit()
    return payment


@blp.route("/mpesa/<int:payment_id>")
@blp.response(200, PaymentOut)
@roles_required("admin", "sales")
def status(payment_id):
    return follow_up(sale_payment(payment_id))


@blp.route("/mpesa/<int:payment_id>/simulate", methods=["POST"])
@blp.arguments(SimulateIn)
@blp.response(200, PaymentOut)
@roles_required("sales")
def simulate(data, payment_id):
    return simulated_outcome(sale_payment(payment_id), data["outcome"])


@blp.route("/mpesa/callback/<string:token>", methods=["POST"])
@blp.response(200)
def callback(token):
    if not hmac.compare_digest(token, mpesa.callback_token()):
        abort(404)
    body = (request.get_json(silent=True) or {}).get("Body", {}).get("stkCallback", {})
    payment = db.session.scalar(
        db.select(MpesaPayment).where(
            MpesaPayment.checkout_request_id == body.get("CheckoutRequestID")
        )
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
