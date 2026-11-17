from datetime import UTC, datetime

from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import fields, validate
from sqlalchemy.orm import selectinload

from app.auth import is_role, roles_required
from app.crud import PageQuery, delete, get_or_404, page_schema, paginate, save
from app.extensions import db
from app.models import Request
from app.models.procurement import REQUEST_STATUSES, URGENCIES
from app.notify import notify, notify_roles
from app.schemas import Schema

blp = Blueprint("requests", __name__, url_prefix="/api/requests", description="Employee requests")

SEE_ALL = ("admin", "procurement")


class RequestSchema(Schema):
    id = fields.Integer(dump_only=True)
    requester_id = fields.Integer(dump_only=True)
    requester_name = fields.String(attribute="requester.full_name", dump_only=True)
    item = fields.String(required=True, validate=validate.Length(min=1, max=200))
    quantity = fields.Integer(required=True, validate=validate.Range(min=1))
    urgency = fields.String(load_default="normal", validate=validate.OneOf(URGENCIES))
    reason = fields.String(required=True, validate=validate.Length(min=1))
    status = fields.String(dump_only=True)
    reviewed_by = fields.Integer(dump_only=True)
    reviewer_name = fields.String(attribute="reviewer.full_name", dump_only=True)
    review_comment = fields.String(dump_only=True)
    reviewed_at = fields.DateTime(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class RequestQuery(PageQuery):
    status = fields.String(load_default=None, validate=validate.OneOf(REQUEST_STATUSES))
    mine = fields.Boolean(load_default=False)  # true: only the signed-in user's own requests


class DecisionSchema(Schema):
    comment = fields.String(load_default=None, validate=validate.Length(max=1000))


class RejectSchema(Schema):
    comment = fields.String(
        required=True,
        validate=validate.Length(min=1, max=1000, error="Say why the request is rejected."),
    )


def visible_request(request_id):
    req = get_or_404(Request, request_id)
    if not is_role(*SEE_ALL) and req.requester_id != current_user.id:
        abort(404, message=f"Request {request_id} not found")
    return req


def own_pending_request(request_id):
    req = visible_request(request_id)
    if req.requester_id != current_user.id:
        abort(403, message="Only the person who made this request can change it.")
    if req.status != "pending":
        abort(409, message="Only pending requests can be changed.")
    return req


def decide(request_id, status, comment):
    req = get_or_404(Request, request_id)
    if req.requester_id == current_user.id:
        abort(403, message="You cannot approve or reject your own request.")
    if req.status != "pending":
        abort(409, message=f"This request is already {req.status}.")
    req.status = status
    req.reviewed_by = current_user.id
    req.review_comment = comment
    req.reviewed_at = datetime.now(UTC)
    note = f": {comment}" if comment else "."
    notify([req.requester_id], f"Your request for {req.item} was {status}{note}")
    return save(req, "Could not save this decision")


@blp.route("/")
@blp.arguments(RequestQuery, location="query")
@blp.response(200, page_schema(RequestSchema))
@roles_required()
def list_requests(args):
    query = (
        db.select(Request)
        .options(selectinload(Request.requester), selectinload(Request.reviewer))
        .order_by(Request.created_at.desc(), Request.id.desc())
    )
    if args["mine"] or not is_role(*SEE_ALL):
        query = query.where(Request.requester_id == current_user.id)
    if args["status"]:
        query = query.where(Request.status == args["status"])
    return paginate(query, args["page"], args["per_page"])


@blp.route("/", methods=["POST"])
@blp.arguments(RequestSchema)
@blp.response(201, RequestSchema)
@roles_required()
def create_request(data):
    req = Request(requester_id=current_user.id, **data)
    urgent = "Urgent request" if data.get("urgency") == "urgent" else "New request"
    notify_roles(
        ("procurement",),
        f"{urgent} from {current_user.full_name}: {data['item']} × {data['quantity']}.",
        exclude=current_user.id,
    )
    return save(req, "Could not save this request")


@blp.route("/<int:request_id>")
@blp.response(200, RequestSchema)
@roles_required()
def get_request(request_id):
    return visible_request(request_id)


@blp.route("/<int:request_id>", methods=["PUT"])
@blp.arguments(RequestSchema)
@blp.response(200, RequestSchema)
@roles_required()
def update_request(data, request_id):
    req = own_pending_request(request_id)
    for key, value in data.items():
        setattr(req, key, value)
    return save(req, "Could not save this request")


@blp.route("/<int:request_id>", methods=["DELETE"])
@blp.response(204)
@roles_required()
def delete_request(request_id):
    delete(own_pending_request(request_id), "Could not delete this request")


@blp.route("/<int:request_id>/approve", methods=["POST"])
@blp.arguments(DecisionSchema)
@blp.response(200, RequestSchema)
@roles_required("procurement")
def approve_request(data, request_id):
    return decide(request_id, "approved", data["comment"])


@blp.route("/<int:request_id>/reject", methods=["POST"])
@blp.arguments(RejectSchema)
@blp.response(200, RequestSchema)
@roles_required("procurement")
def reject_request(data, request_id):
    return decide(request_id, "rejected", data["comment"])
