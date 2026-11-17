"""/api/repairs — anyone reports a problem with an asset they hold; Inventory fixes it.

Status moves forward only: submitted → in_progress → done.
  in_progress: the asset is marked "in_repair".
  done:        the asset goes back to its holder ("assigned"), or "available" if nobody holds it.
The person who reported it is notified at each step.
"""

from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import fields, validate
from sqlalchemy.orm import selectinload

from app.auth import is_role, roles_required
from app.crud import PageQuery, get_or_404, page_schema, paginate
from app.extensions import db
from app.models import Asset, Repair
from app.models.assets import REPAIR_STATUSES
from app.notify import notify, notify_roles
from app.schemas import Schema

blp = Blueprint("repairs", __name__, url_prefix="/api/repairs", description="Asset repairs")

MANAGERS = ("admin", "inventory")
STATUS_WORDS = {"submitted": "submitted", "in_progress": "in progress", "done": "done"}


class RepairIn(Schema):
    asset_id = fields.Integer(required=True)
    description = fields.String(
        required=True,
        validate=validate.Length(min=5, max=1000, error="Describe the problem (5+ characters)."),
    )


class StatusIn(Schema):
    status = fields.String(required=True, validate=validate.OneOf(REPAIR_STATUSES))


class RepairOut(Schema):
    id = fields.Integer()
    reference = fields.Method("get_reference")
    asset_id = fields.Integer()
    asset_code = fields.String(attribute="asset.asset_code")
    asset_name = fields.String(attribute="asset.name")
    reported_by = fields.Integer()
    reporter_name = fields.String(attribute="reporter.full_name")
    description = fields.String()
    status = fields.String()
    created_at = fields.DateTime()
    updated_at = fields.DateTime()

    def get_reference(self, repair):
        return f"REP-{repair.id:03d}"


class RepairQuery(PageQuery):
    status = fields.String(load_default=None, validate=validate.OneOf(REPAIR_STATUSES))


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
    """Admin and Inventory see every repair; everyone else sees the ones they reported."""
    query = (
        db.select(Repair)
        .options(selectinload(Repair.asset), selectinload(Repair.reporter))
        .order_by(Repair.created_at.desc(), Repair.id.desc())
    )
    if not is_role(*MANAGERS):
        query = query.where(Repair.reported_by == current_user.id)
    if args["status"]:
        query = query.where(Repair.status == args["status"])
    return paginate(query, args["page"], args["per_page"])


@blp.route("/", methods=["POST"])
@blp.arguments(RepairIn)
@blp.response(201, RepairOut)
@roles_required()
def report_repair(data):
    asset = db.session.get(Asset, data["asset_id"])
    if asset is None or (not is_role(*MANAGERS) and asset.assigned_to != current_user.id):
        abort(400, message="Choose an asset you hold.")
    open_repair = db.session.scalar(
        db.select(Repair).where(Repair.asset_id == asset.id, Repair.status != "done")
    )
    if open_repair:
        abort(409, message=f"{asset.name} already has an open repair (REP-{open_repair.id:03d}).")
    repair = Repair(asset_id=asset.id, reported_by=current_user.id, description=data["description"])
    db.session.add(repair)
    db.session.flush()
    notify_roles(
        MANAGERS,
        f"Repair REP-{repair.id:03d}: {asset.name} ({asset.asset_code}) reported by "
        f"{current_user.full_name}.",
        exclude=current_user.id,
    )
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
    repair = get_or_404(Repair, repair_id)
    order = list(REPAIR_STATUSES)
    if order.index(data["status"]) <= order.index(repair.status):
        abort(409, message=f"This repair is already {STATUS_WORDS[repair.status]}.")
    repair.status = data["status"]
    asset = repair.asset
    if data["status"] == "in_progress":
        asset.status = "in_repair"
    elif data["status"] == "done":
        asset.status = "assigned" if asset.assigned_to else "available"
    notify(
        [repair.reported_by],
        f"Repair REP-{repair.id:03d} ({asset.name}) is {STATUS_WORDS[repair.status]}.",
    )
    db.session.commit()
    return repair