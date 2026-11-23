from zoneinfo import available_timezones

from flask_jwt_extended import current_user
from flask_smorest import Blueprint
from marshmallow import fields, validate

from app.audit import audit, diff
from app.auth import is_role, roles_required
from app.extensions import db
from app.models.business import new_join_code
from app.schemas import Schema

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
