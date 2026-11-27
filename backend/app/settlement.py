import uuid
from datetime import UTC, datetime, timedelta

from app import mpesa
from app.audit import audit
from app.billing import extend
from app.extensions import db
from app.models import Business, MpesaPayment
from app.notify import notify_roles
from app.resources.sales import SaleProblem, record_sale

CHECK_AFTER = timedelta(seconds=20)
CHECK_EVERY = timedelta(seconds=10)
GIVE_UP_AFTER = timedelta(minutes=3)
OUTCOMES = {
    1: ("failed", "The M-Pesa balance is too low."),
    1032: ("cancelled", "The M-Pesa prompt was cancelled on the phone."),
    1037: ("failed", "The phone did not answer in time."),
    2001: ("failed", "The wrong M-Pesa PIN was entered."),
}


def now():
    return datetime.now(UTC)


def account_for(payment):
    if payment.purpose == "subscription":
        return mpesa.platform_account()
    return mpesa.business_account(db.session.get(Business, payment.business_id))


def send_prompt(payment, account, reference, description):
    payment.simulated = account.mode == "simulate"
    if payment.simulated:
        payment.checkout_request_id = f"SIM-{uuid.uuid4().hex}"
        return
    checkout, merchant = mpesa.stk_push(
        account, payment.phone, payment.amount, reference, description
    )
    payment.checkout_request_id, payment.merchant_request_id = checkout, merchant


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
    if payment.purpose == "subscription":
        _renew(payment, receipt)
    else:
        _complete_sale(payment, receipt)
    db.session.commit()
    return payment


def _complete_sale(payment, receipt):
    wanted = {int(pid): quantity for pid, quantity in payment.items.items()}
    try:
        with db.session.begin_nested():
            sale = record_sale(
                wanted, "mpesa", payment.attendant_id, payment.idempotency_key, receipt
            )
    except SaleProblem as problem:
        payment.problem = (
            f"M-Pesa {receipt} for {payment.amount} was received, but the sale could not be "
            f"completed: {problem.message} Sell it again or refund the customer."
        )
        notify_roles(("admin", "sales"), payment.problem, link="/sales")
        return
    payment.sale_id = sale.id
    audit(
        "paid",
        "sale",
        sale.id,
        f"{sale.reference} paid by M-Pesa {receipt} ({payment.amount})",
        user_id=payment.attendant_id,
    )


def _renew(payment, receipt):
    business = db.session.get(Business, payment.business_id)
    until = extend(business, payment.months)
    plural = "s" if payment.months != 1 else ""
    audit(
        "paid",
        "business",
        business.id,
        f"Subscription paid for {payment.months} month{plural} (M-Pesa {receipt})",
        user_id=payment.attendant_id,
    )
    notify_roles(
        ("admin",),
        f"Thank you. {business.name}'s StockPilot subscription is paid until "
        f"{until:%d %B %Y} (M-Pesa {receipt}, KES {payment.amount:,}).",
        link="/billing",
        email_subject="StockPilot subscription receipt",
    )


def follow_up(payment):
    if payment.status != "pending" or payment.simulated:
        return payment
    age = now() - payment.created_at
    if age < CHECK_AFTER or (payment.checked_at and now() - payment.checked_at < CHECK_EVERY):
        return payment
    payment.checked_at = now()
    db.session.commit()
    try:
        answer = mpesa.stk_query(account_for(payment), payment.checkout_request_id)
    except mpesa.MpesaError:
        if age > GIVE_UP_AFTER:
            return settle(payment, 1037, "No answer")
        return payment
    code = answer.get("ResultCode")
    if code is None or int(code) == 0:
        return payment
    return settle(payment, int(code), answer.get("ResultDesc", "Failed"))
