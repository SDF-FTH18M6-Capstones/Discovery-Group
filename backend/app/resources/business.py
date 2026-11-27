from zoneinfo import available_timezones

from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import fields, validate

from app import mpesa
from app.audit import audit, diff
from app.auth import is_role, roles_required
from app.extensions import db
from app.models.business import new_join_code
from app.schemas import Schema
from app.vault import seal

blp = Blueprint("business", __name__, url_prefix="/api/business", description="Business settings")

ZONES = sorted(available_timezones())


class BusinessSchema(Schema):
    id = fields.Integer(dump_only=True)
    name = fields.String(required=True, validate=validate.Length(min=2, max=150))
    timezone = fields.String(
        required=True, validate=validate.OneOf(ZONES, error="Choose a time zone from the list.")
    )
    currency = fields.String(
        required=True,
        validate=validate.Regexp(r"^[A-Z]{3}$", error="Use a 3-letter currency code, e.g. KES."),
    )
    vat_rate = fields.Decimal(
        required=True, places=2, as_string=True, validate=validate.Range(min=0, max=99)
    )
    phone = fields.String(allow_none=True, load_default=None, validate=validate.Length(max=30))
    email = fields.Email(allow_none=True, load_default=None)
    address = fields.String(allow_none=True, load_default=None, validate=validate.Length(max=300))
    receipt_footer = fields.String(
        allow_none=True, load_default=None, validate=validate.Length(max=300)
    )
    daily_summary = fields.Boolean(load_default=True)
    join_code = fields.Method("get_join_code", dump_only=True)
    created_at = fields.DateTime(dump_only=True)

    def get_join_code(self, business):
        return business.join_code if is_role("admin") else None


class JoinCodeSchema(Schema):
    join_code = fields.String()


@blp.route("")
@blp.response(200, BusinessSchema)
@roles_required()
def get_business():
    return current_user.business


@blp.route("", methods=["PUT"])
@blp.arguments(BusinessSchema)
@blp.response(200, BusinessSchema)
@roles_required("admin")
def update_business(data):
    business = current_user.business
    for key in ("phone", "email", "address", "receipt_footer"):
        data[key] = data[key] or None
    changes = diff(business, data)
    for key, value in data.items():
        setattr(business, key, value)
    if changes:
        audit("updated", "business", business.id, "Business settings changed", changes)
    db.session.commit()
    return business


@blp.route("/join-code", methods=["POST"])
@blp.response(200, JoinCodeSchema)
@roles_required("admin")
def new_code():
    business = current_user.business
    business.join_code = new_join_code()
    audit("updated", "business", business.id, "Join code changed")
    db.session.commit()
    return {"join_code": business.join_code}


class MpesaSettings(Schema):
    mode = fields.String(required=True, validate=validate.OneOf(mpesa.MODES))
    type = fields.String(
        required=True, attribute="mpesa_type", validate=validate.OneOf(("paybill", "till"))
    )
    shortcode = fields.String(
        allow_none=True,
        load_default=None,
        attribute="mpesa_shortcode",
        validate=validate.Regexp(r"^\d{5,7}$", error="Use the 5 to 7 digit number from Safaricom."),
    )
    till = fields.String(
        allow_none=True,
        load_default=None,
        attribute="mpesa_till",
        validate=validate.Regexp(r"^\d{5,7}$", error="Use the 5 to 7 digit till number."),
    )
    passkey = fields.String(load_only=True, load_default="", validate=validate.Length(max=200))
    consumer_key = fields.String(load_only=True, load_default="", validate=validate.Length(max=200))
    consumer_secret = fields.String(
        load_only=True, load_default="", validate=validate.Length(max=200)
    )
    has_passkey = fields.Boolean(dump_only=True)
    has_keys = fields.Boolean(dump_only=True)


def mpesa_view(business):
    return {
        "mode": mpesa.business_account(business).mode,
        "mpesa_type": business.mpesa_type,
        "mpesa_shortcode": business.mpesa_shortcode,
        "mpesa_till": business.mpesa_till,
        "has_passkey": bool(business.mpesa_passkey),
        "has_keys": bool(business.mpesa_consumer_key and business.mpesa_consumer_secret),
    }


@blp.route("/mpesa")
@blp.response(200, MpesaSettings)
@roles_required("admin")
def get_mpesa():
    return mpesa_view(current_user.business)


@blp.route("/mpesa", methods=["PUT"])
@blp.arguments(MpesaSettings)
@blp.response(200, MpesaSettings)
@roles_required("admin")
def update_mpesa(data):
    business = current_user.business
    business.mpesa_type = data["mpesa_type"]
    business.mpesa_shortcode = data["mpesa_shortcode"] or None
    business.mpesa_till = data["mpesa_till"] or None
    for field in ("passkey", "consumer_key", "consumer_secret"):
        if data[field].strip():
            setattr(business, f"mpesa_{field}", seal(data[field].strip()))
    if data["mode"] in ("sandbox", "live"):
        missing = [
            label
            for label, present in (
                ("Paybill or store number", business.mpesa_shortcode),
                ("till number", business.mpesa_type == "paybill" or business.mpesa_till),
                ("passkey", business.mpesa_passkey),
                ("consumer key", business.mpesa_consumer_key),
                ("consumer secret", business.mpesa_consumer_secret),
            )
            if not present
        ]
        if missing:
            db.session.rollback()
            abort(422, message=f"To take real M-Pesa payments, add the {', '.join(missing)}.")
    business.mpesa_mode = data["mode"]
    audit(
        "updated",
        "business",
        business.id,
        f"M-Pesa settings changed ({data['mode']}, {data['mpesa_type']})",
    )
    db.session.commit()
    return mpesa_view(business)
