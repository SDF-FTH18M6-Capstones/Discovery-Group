from datetime import UTC, datetime

from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import fields, validate
from sqlalchemy.orm import selectinload

from app.audit import audit
from app.auth import is_role, roles_required
from app.crud import PageQuery, find, get_or_404, page_schema, paginate, save
from app.extensions import db
from app.models import Product, Request
from app.models.procurement import (
    ACTIVE_REQUEST_STATUSES,
    REQUEST_STATUSES,
    URGENCIES,
)
from app.notify import notify, notify_roles
from app.schemas import Schema
from app.shoptime import day_bounds, shop_today
from app.timeline import TimelineEntry, record_timeline

blp = Blueprint("requests", __name__, url_prefix="/api/requests", description="Employee requests")

SEE_ALL = ("admin", "procurement")
DECIDERS = ("procurement",)


class PurchaseBrief(Schema):
    id = fields.Integer()
    reference = fields.String()
    status = fields.String()


class RequestSchema(Schema):
    id = fields.Integer(dump_only=True)
    reference = fields.String(dump_only=True)
    requester_id = fields.Integer(dump_only=True)
    requester_name = fields.String(attribute="requester.full_name", dump_only=True)
    product_id = fields.Integer(allow_none=True, load_default=None)
    product_sku = fields.String(attribute="product.sku", dump_only=True, allow_none=True)
    item = fields.String(required=True, validate=validate.Length(min=1, max=200))
    quantity = fields.Integer(required=True, validate=validate.Range(min=1))
    urgency = fields.String(load_default="normal", validate=validate.OneOf(URGENCIES))
    reason = fields.String(required=True, validate=validate.Length(min=1))
    status = fields.String(dump_only=True)
    reviewed_by = fields.Integer(dump_only=True)
    reviewer_name = fields.String(attribute="reviewer.full_name", dump_only=True)
    review_comment = fields.String(dump_only=True)
    reviewed_at = fields.DateTime(dump_only=True)
    fulfilled_at = fields.DateTime(dump_only=True)
    cancelled_at = fields.DateTime(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    purchases = fields.List(fields.Nested(PurchaseBrief), dump_only=True)


class RequestQuery(PageQuery):
    status = fields.String(load_default=None, validate=validate.OneOf(REQUEST_STATUSES))
    mine = fields.Boolean(load_default=False)
    tab = fields.String(load_default=None, validate=validate.OneOf(("active", "completed")))
    urgency = fields.String(load_default=None, validate=validate.OneOf(URGENCIES))
    decided_today = fields.Boolean(load_default=False)
    sort = fields.String(load_default="newest", validate=validate.OneOf(("newest", "urgency")))
    search = fields.String(load_default=None)


class DecisionSchema(Schema):
    comment = fields.String(load_default=None, validate=validate.Length(max=1000))


class RejectSchema(Schema):
    comment = fields.String(
        required=True,
        validate=validate.Length(min=1, max=1000, error="Say why the request is rejected."),
    )


URGENCY_ORDER = db.case(
    {"urgent": 0, "high": 1, "normal": 2, "low": 3}, value=Request.urgency, else_=4
)


def with_people(query):
    return query.options(
        selectinload(Request.requester),
        selectinload(Request.reviewer),
        selectinload(Request.product),
        selectinload(Request.purchases),
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


def check_product(product_id):
    if product_id is not None and find(Product, product_id) is None:
        abort(400, message=f"Product {product_id} does not exist")


def link_for(req):
    return f"/requests?open={req.id}"


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
    notify(
        [req.requester_id],
        f"Your request {req.reference} for {req.item} was {status}{note}",
        link=link_for(req),
        email_subject=f"Your request {req.reference} was {status}",
    )
    audit(
        status,
        "request",
        req.id,
        f"{status.capitalize()} by {current_user.full_name}" + (f": {comment}" if comment else ""),
        {"status": ["pending", status]},
    )
    return save(req, "Could not save this decision")


@blp.route("/")
@blp.arguments(RequestQuery, location="query")
@blp.response(200, page_schema(RequestSchema))
@roles_required()
def list_requests(args):
    query = with_people(db.select(Request))
    if args["sort"] == "urgency":
        query = query.order_by(URGENCY_ORDER, Request.created_at, Request.id)
    else:
        query = query.order_by(Request.created_at.desc(), Request.id.desc())
    if args["mine"] or not is_role(*SEE_ALL):
        query = query.where(Request.requester_id == current_user.id)
    if args["status"]:
        query = query.where(Request.status == args["status"])
    if args["tab"] == "active":
        query = query.where(Request.status.in_(ACTIVE_REQUEST_STATUSES))
    elif args["tab"] == "completed":
        query = query.where(Request.status.not_in(ACTIVE_REQUEST_STATUSES))
    if args["urgency"]:
        query = query.where(Request.urgency == args["urgency"])
    if args["decided_today"]:
        start, end = day_bounds(shop_today())
        query = query.where(Request.reviewed_at >= start, Request.reviewed_at < end)
    if args["search"]:
        term = f"%{args['search']}%"
        digits = args["search"].upper().removeprefix("REQ-").lstrip("0")
        match = Request.item.ilike(term)
        if digits.isdigit():
            match = match | (Request.number == int(digits))
        query = query.where(match)
    return paginate(query, args["page"], args["per_page"])


@blp.route("/", methods=["POST"])
@blp.arguments(RequestSchema)
@blp.response(201, RequestSchema)
@roles_required()
def create_request(data):
    check_product(data["product_id"])
    req = Request(requester_id=current_user.id, **data)
    db.session.add(req)
    db.session.flush()
    urgent = data.get("urgency") == "urgent"
    notify_roles(
        ("procurement",),
        f"{'Urgent request' if urgent else 'New request'} {req.reference} from "
        f"{current_user.full_name}: {data['item']} × {data['quantity']}.",
        exclude=current_user.id,
        link=f"/approvals?open={req.id}",
        email_subject=f"Urgent request {req.reference}: {data['item']}" if urgent else None,
    )
    audit("submitted", "request", req.id, f"Submitted by {current_user.full_name}")
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
    check_product(data["product_id"])
    for key, value in data.items():
        setattr(req, key, value)
    audit("edited", "request", req.id, f"Edited by {current_user.full_name}")
    return save(req, "Could not save this request")


@blp.route("/<int:request_id>/cancel", methods=["POST"])
@blp.response(200, RequestSchema)
@roles_required()
def cancel_request(request_id):
    return do_cancel(request_id)


def do_cancel(request_id):
    req = own_pending_request(request_id)
    req.status = "cancelled"
    req.cancelled_at = datetime.now(UTC)
    audit(
        "cancelled",
        "request",
        req.id,
        "Cancelled by the requester",
        {"status": ["pending", "cancelled"]},
    )
    return save(req, "Could not cancel this request")


@blp.route("/<int:request_id>", methods=["DELETE"])
@blp.response(204)
@roles_required()
def delete_request(request_id):
    do_cancel(request_id)


@blp.route("/<int:request_id>/approve", methods=["POST"])
@blp.arguments(DecisionSchema)
@blp.response(200, RequestSchema)
@roles_required(*DECIDERS)
def approve_request(data, request_id):
    return decide(request_id, "approved", data["comment"])


@blp.route("/<int:request_id>/reject", methods=["POST"])
@blp.arguments(RejectSchema)
@blp.response(200, RequestSchema)
@roles_required(*DECIDERS)
def reject_request(data, request_id):
    return decide(request_id, "rejected", data["comment"])


def fulfil(req, how):
    if req.status != "approved":
        return
    req.status = "fulfilled"
    req.fulfilled_at = datetime.now(UTC)
    notify(
        [req.requester_id],
        f"Your request {req.reference} for {req.item} has been fulfilled.",
        link=link_for(req),
        email_subject=f"Your request {req.reference} is ready",
    )
    audit("fulfilled", "request", req.id, how, {"status": ["approved", "fulfilled"]})


@blp.route("/<int:request_id>/fulfil", methods=["POST"])
@blp.response(200, RequestSchema)
@roles_required(*SEE_ALL)
def fulfil_request(request_id):
    req = get_or_404(Request, request_id)
    if req.status != "approved":
        abort(409, message="Only approved requests can be marked fulfilled.")
    fulfil(req, f"Fulfilled by {current_user.full_name}")
    return save(req, "Could not save this request")


@blp.route("/<int:request_id>/timeline")
@blp.arguments(PageQuery, location="query")
@blp.response(200, page_schema(TimelineEntry))
@roles_required()
def timeline(args, request_id):
    visible_request(request_id)
    return record_timeline("request", request_id, args["page"], args["per_page"])
