"""/api/requests — employee requests. GET (list, filter), POST, GET one, PUT, DELETE.

Sprint 2 keeps this to plain CRUD. Approving and rejecting (Procurement Manager only) and taking
the requester from the signed-in user arrive with authentication in a later sprint.
"""

from flask_smorest import Blueprint, abort
from marshmallow import Schema, fields, validate

from app.crud import PageQuery, delete, get_or_404, page_schema, paginate, save
from app.extensions import db
from app.models import Request, User
from app.models.procurement import REQUEST_STATUSES, URGENCIES

blp = Blueprint("requests", __name__, url_prefix="/api/requests", description="Employee requests")


class RequestSchema(Schema):
    id = fields.Integer(dump_only=True)
    requester_id = fields.Integer(required=True)
    requester_name = fields.String(attribute="requester.full_name", dump_only=True)
    item = fields.String(required=True, validate=validate.Length(min=1, max=200))
    quantity = fields.Integer(required=True, validate=validate.Range(min=1))
    urgency = fields.String(load_default="normal", validate=validate.OneOf(URGENCIES))
    reason = fields.String(required=True, validate=validate.Length(min=1))
    status = fields.String(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class RequestQuery(PageQuery):
    status = fields.String(load_default=None, validate=validate.OneOf(REQUEST_STATUSES))


def check_requester(user_id):
    if db.session.get(User, user_id) is None:
        abort(400, message=f"User {user_id} does not exist")


@blp.route("/")
@blp.arguments(RequestQuery, location="query")
@blp.response(200, page_schema(RequestSchema))
def list_requests(args):
    query = db.select(Request).order_by(Request.created_at.desc(), Request.id.desc())
    if args["status"]:
        query = query.where(Request.status == args["status"])
    return paginate(query, args["page"], args["per_page"])


@blp.route("/", methods=["POST"])
@blp.arguments(RequestSchema)
@blp.response(201, RequestSchema)
def create_request(data):
    check_requester(data["requester_id"])
    return save(Request(**data), "Could not save this request")


@blp.route("/<int:request_id>")
@blp.response(200, RequestSchema)
def get_request(request_id):
    return get_or_404(Request, request_id)


@blp.route("/<int:request_id>", methods=["PUT"])
@blp.arguments(RequestSchema)
@blp.response(200, RequestSchema)
def update_request(data, request_id):
    req = get_or_404(Request, request_id)
    if req.status != "pending":
        abort(409, message="Only pending requests can be edited")
    check_requester(data["requester_id"])
    for key, value in data.items():
        setattr(req, key, value)
    return save(req, "Could not save this request")


@blp.route("/<int:request_id>", methods=["DELETE"])
@blp.response(204)
def delete_request(request_id):
    req = get_or_404(Request, request_id)
    if req.status != "pending":
        abort(409, message="Only pending requests can be deleted")
    delete(req, "Could not delete this request")