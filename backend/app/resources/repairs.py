from datetime import UTC, datetime

from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import ValidationError, fields, validate, validates_schema
from sqlalchemy.orm import selectinload

from app.audit import audit
from app.auth import is_role, roles_required
from app.crud import PageQuery, find, get_or_404, page_schema, paginate
from app.extensions import db
from app.models import Asset, Repair
from app.models.assets import OPEN_REPAIR_STATUSES, REPAIR_STATUSES, REPAIR_URGENCIES
from app.notify import notify, notify_roles
from app.schemas import Schema
from app.timeline import TimelineEntry, record_timeline

blp = Blueprint("repairs", __name__, url_prefix="/api/repairs", description="Asset repairs")

MANAGERS = ("admin", "inventory")
STATUS_WORDS = {
    "submitted": "submitted",
    "in_progress": "in progress",
    "done": "completed",
    "rejected": "rejected",
}
NEXT = {"submitted": ("in_progress", "rejected"), "in_progress": ("done",)}
money = {"places": 2, "as_string": True}


class RepairIn(Schema):
    asset_id = fields.Integer(required=True)
    description = fields.String(
        required=True,
        validate=validate.Length(min=5, max=1000, error="Describe the problem (5+ characters)."),
    )
    urgency = fields.String(load_default="normal", validate=validate.OneOf(REPAIR_URGENCIES))


class StatusIn(Schema):
    status = fields.String(required=True, validate=validate.OneOf(REPAIR_STATUSES))
    resolution = fields.String(
        allow_none=True, load_default=None, validate=validate.Length(max=2000)
    )
    cost = fields.Decimal(
        allow_none=True, load_default=None, places=2, validate=validate.Range(min=0)
    )

    @validates_schema
    def needs_resolution(self, data, **kwargs):
        if data["status"] in ("done", "rejected") and not (data.get("resolution") or "").strip():
            word = "what was done" if data["status"] == "done" else "why it is rejected"
            raise ValidationError(f"Say {word}.", "resolution")


class RepairOut(Schema):
    id = fields.Integer()
    reference = fields.String()
    asset_id = fields.Integer()
    asset_code = fields.String(attribute="asset.asset_code")
    asset_name = fields.String(attribute="asset.name")
    reported_by = fields.Integer()
    reporter_name = fields.String(attribute="reporter.full_name")
    handler_name = fields.String(attribute="handler.full_name", allow_none=True)
    description = fields.String()
    urgency = fields.String()
    status = fields.String()
    resolution = fields.String(allow_none=True)
    cost = fields.Decimal(allow_none=True, **money)
    started_at = fields.DateTime(allow_none=True)
    closed_at = fields.DateTime(allow_none=True)
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


class RepairQuery(PageQuery):
    status = fields.String(load_default=None, validate=validate.OneOf((*REPAIR_STATUSES, "open")))
    asset_id = fields.Integer(load_default=None)


def visible(repair_id):
    repair = get_or_404(Repair, repair_id)
    if not is_role(*MANAGERS) and repair.reported_by != current_user.id:
        abort(404, message=f"Repair {repair_id} not found")
    return repair


@blp.route("/")
@blp.arguments(RepairQuery, location="query")
@blp.response(200, page_schema(RepairOut))
@roles_required()
def list_repairs(args):
    query = (
        db.select(Repair)
        .options(
            selectinload(Repair.asset),
            selectinload(Repair.reporter),
            selectinload(Repair.handler),
        )
        .order_by(Repair.created_at.desc(), Repair.id.desc())
    )
    if not is_role(*MANAGERS):
        query = query.where(Repair.reported_by == current_user.id)
    if args["status"] == "open":
        query = query.where(Repair.status.in_(OPEN_REPAIR_STATUSES))
    elif args["status"]:
        query = query.where(Repair.status == args["status"])
    if args["asset_id"]:
        query = query.where(Repair.asset_id == args["asset_id"])
    return paginate(query, args["page"], args["per_page"])


@blp.route("/", methods=["POST"])
@blp.arguments(RepairIn)
@blp.response(201, RepairOut)
@roles_required()
def report_repair(data):
    asset = find(Asset, data["asset_id"])
    if asset is None or (not is_role(*MANAGERS) and asset.assigned_to != current_user.id):
        abort(400, message="Choose an asset you hold.")
    if asset.status == "retired":
        abort(409, message=f"{asset.name} is retired.")
    open_repair = db.session.scalar(
        db.select(Repair).where(
            Repair.asset_id == asset.id, Repair.status.in_(OPEN_REPAIR_STATUSES)
        )
    )
    if open_repair:
        abort(409, message=f"{asset.name} already has an open repair ({open_repair.reference}).")
    repair = Repair(
        asset_id=asset.id,
        reported_by=current_user.id,
        description=data["description"],
        urgency=data["urgency"],
    )
    db.session.add(repair)
    db.session.flush()
    urgent = data["urgency"] == "urgent"
    notify_roles(
        MANAGERS,
        f"Repair {repair.reference}: {asset.name} ({asset.asset_code}) reported by "
        f"{current_user.full_name}.",
        exclude=current_user.id,
        link=f"/repairs?open={repair.id}",
        email_subject=f"Urgent repair {repair.reference}: {asset.name}" if urgent else None,
    )
    audit("repair", "asset", asset.id, f"{repair.reference} reported: {data['description']}")
    db.session.commit()
    return repair


@blp.route("/<int:repair_id>")
@blp.response(200, RepairOut)
@roles_required()
def get_repair(repair_id):
    return visible(repair_id)


@blp.route("/<int:repair_id>/status", methods=["PUT"])
@blp.arguments(StatusIn)
@blp.response(200, RepairOut)
@roles_required(*MANAGERS)
def move_repair(data, repair_id):
    repair = db.session.scalar(db.select(Repair).where(Repair.id == repair_id).with_for_update())
    if repair is None:
        abort(404, message=f"Repair {repair_id} not found")
    new = data["status"]
    if new not in NEXT.get(repair.status, ()):
        db.session.rollback()
        if repair.status in ("done", "rejected") or new == repair.status:
            abort(409, message=f"This repair is already {STATUS_WORDS[repair.status]}.")
        abort(
            409,
            message=f"A {STATUS_WORDS[repair.status]} repair cannot become {STATUS_WORDS[new]}.",
        )
    old = repair.status
    asset = repair.asset
    now = datetime.now(UTC)
    repair.status = new
    repair.handled_by = current_user.id
    if new == "in_progress":
        repair.started_at = now
        repair.asset_status_before = asset.status
        asset.status = "in_repair"
    else:
        repair.closed_at = now
        repair.resolution = data["resolution"].strip()
        if new == "done":
            repair.cost = data["cost"]
            if asset.status == "in_repair":
                asset.status = repair.asset_status_before or (
                    "assigned" if asset.assigned_to else "available"
                )
    note = f": {repair.resolution}" if repair.resolution and new != "in_progress" else ""
    notify(
        [repair.reported_by],
        f"Repair {repair.reference} ({asset.name}) is {STATUS_WORDS[new]}{note}.",
        link=f"/repairs?open={repair.id}",
        email_subject=f"Repair {repair.reference} is {STATUS_WORDS[new]}",
    )
    cost = f" (cost {repair.cost})" if new == "done" and repair.cost is not None else ""
    audit(
        "repair",
        "asset",
        asset.id,
        f"{repair.reference} {STATUS_WORDS[new]}{note}{cost}",
        {"status": [old, new]},
    )
    db.session.commit()
    return repair


@blp.route("/<int:repair_id>/timeline")
@blp.arguments(PageQuery, location="query")
@blp.response(200, page_schema(TimelineEntry))
@roles_required()
def timeline(args, repair_id):
    repair = visible(repair_id)
    return record_timeline("asset", repair.asset_id, args["page"], args["per_page"])
