from datetime import UTC, datetime

from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import fields, validate
from sqlalchemy.orm import selectinload

from app.audit import audit, diff
from app.auth import is_role, roles_required
from app.crud import PageQuery, delete, find, get_or_404, page_schema, paginate, save
from app.extensions import db
from app.images import read_upload, remove_photo, replace_photo
from app.models import Asset, AssetAssignment, AssetCategory, User
from app.models.assets import ASSET_STATUSES, CONDITIONS
from app.notify import notify
from app.schemas import Schema
from app.shoptime import shop_today
from app.timeline import TimelineEntry, record_timeline

MANAGERS = ("inventory",)
SEE_ALL = ("admin", "inventory")

blp = Blueprint("assets", __name__, url_prefix="/api/assets", description="Assets")
categories_blp = Blueprint(
    "asset_categories", __name__, url_prefix="/api/asset-categories", description="Asset categories"
)
money = {"places": 2, "as_string": True}


class AssignmentOut(Schema):
    id = fields.Integer()
    user_id = fields.Integer()
    user_name = fields.String(attribute="user.full_name")
    assigned_by_name = fields.String(attribute="assigner.full_name")
    assigned_at = fields.DateTime()
    expected_return = fields.Date(allow_none=True)
    condition_out = fields.String()
    returned_at = fields.DateTime(allow_none=True)
    received_by_name = fields.String(attribute="receiver.full_name", allow_none=True)
    condition_in = fields.String(allow_none=True)
    return_notes = fields.String(allow_none=True)
    is_overdue = fields.Method("get_overdue")

    def get_overdue(self, assignment):
        return bool(
            assignment.returned_at is None
            and assignment.expected_return
            and assignment.expected_return < shop_today()
        )


class RepairBrief(Schema):
    id = fields.Integer()
    reference = fields.String()
    status = fields.String()


class AssetSchema(Schema):
    id = fields.Integer(dump_only=True)
    asset_code = fields.String(dump_only=True)
    barcode = fields.String(dump_only=True)
    name = fields.String(required=True, validate=validate.Length(min=1, max=150))
    category_id = fields.Integer(allow_none=True, load_default=None)
    category_name = fields.String(attribute="category.name", dump_only=True, allow_none=True)
    serial_number = fields.String(
        allow_none=True, load_default=None, validate=validate.Length(max=100)
    )
    purchase_date = fields.Date(allow_none=True, load_default=None)
    purchase_cost = fields.Decimal(
        allow_none=True, load_default=None, validate=validate.Range(min=0), **money
    )
    condition = fields.String(load_default="good", validate=validate.OneOf(CONDITIONS))
    notes = fields.String(allow_none=True, load_default=None, validate=validate.Length(max=2000))
    image_url = fields.String(dump_only=True)
    status = fields.String(dump_only=True)
    assigned_to = fields.Integer(allow_none=True, load_default=None)
    expected_return = fields.Date(allow_none=True, load_default=None, load_only=True)
    holder_name = fields.String(attribute="holder.full_name", dump_only=True, allow_none=True)
    current_assignment = fields.Nested(AssignmentOut, dump_only=True, allow_none=True)
    open_repair = fields.Nested(RepairBrief, dump_only=True, allow_none=True)
    created_at = fields.DateTime(dump_only=True)


class AssetQuery(PageQuery):
    search = fields.String(load_default=None)
    status = fields.String(load_default=None, validate=validate.OneOf(ASSET_STATUSES))
    category_id = fields.Integer(load_default=None)
    overdue = fields.Boolean(load_default=False)
    mine = fields.Boolean(load_default=False)


class AssignIn(Schema):
    user_id = fields.Integer(required=True)
    expected_return = fields.Date(allow_none=True, load_default=None)
    condition = fields.String(required=True, validate=validate.OneOf(CONDITIONS))


class ReturnIn(Schema):
    condition = fields.String(required=True, validate=validate.OneOf(CONDITIONS))
    notes = fields.String(allow_none=True, load_default=None, validate=validate.Length(max=1000))


class AssetCategorySchema(Schema):
    id = fields.Integer(dump_only=True)
    name = fields.String(required=True, validate=validate.Length(min=1, max=100))


def with_details(query):
    return query.options(
        selectinload(Asset.holder),
        selectinload(Asset.category),
        selectinload(Asset.current_assignment).selectinload(AssetAssignment.user),
        selectinload(Asset.current_assignment).selectinload(AssetAssignment.assigner),
        selectinload(Asset.open_repair),
    )


def load(asset_id):
    db.session.expire_all()
    return db.session.scalar(with_details(db.select(Asset).where(Asset.id == asset_id)))


def active_user(user_id):
    user = find(User, user_id)
    if user is None or not user.is_active:
        abort(400, message=f"User {user_id} does not exist or is deactivated")
    return user


def check_category(category_id):
    if category_id is not None and find(AssetCategory, category_id) is None:
        abort(400, message=f"Asset category {category_id} does not exist")


def visible(asset_id):
    asset = get_or_404(Asset, asset_id)
    if not is_role(*SEE_ALL) and asset.assigned_to != current_user.id:
        abort(404, message=f"Asset {asset_id} not found")
    return asset


@blp.route("/")
@blp.arguments(AssetQuery, location="query")
@blp.response(200, page_schema(AssetSchema))
@roles_required()
def list_assets(args):
    query = with_details(db.select(Asset)).order_by(Asset.number)
    if args["mine"] or not is_role(*SEE_ALL):
        query = query.where(Asset.assigned_to == current_user.id)
    if args["search"]:
        term = f"%{args['search']}%"
        query = query.where(
            Asset.name.ilike(term)
            | Asset.asset_code.ilike(term)
            | Asset.serial_number.ilike(term)
            | (Asset.barcode == args["search"])
        )
    if args["status"]:
        query = query.where(Asset.status == args["status"])
    if args["category_id"]:
        query = query.where(Asset.category_id == args["category_id"])
    if args["overdue"]:
        query = query.where(
            Asset.current_assignment.has(AssetAssignment.expected_return < shop_today())
        )
    return paginate(query, args["page"], args["per_page"])


@blp.route("/lookup/<string:code>")
@blp.response(200, AssetSchema)
@roles_required(*SEE_ALL)
def lookup(code):
    asset_id = db.session.scalar(
        db.select(Asset.id).where((Asset.barcode == code) | (Asset.asset_code == code.upper()))
    )
    if asset_id is None:
        abort(404, message=f"No asset with code {code}")
    return load(asset_id)


def open_assignment(asset, user, condition, expected_return):
    if expected_return and expected_return < shop_today():
        abort(400, message="The expected return date is in the past.")
    db.session.add(
        AssetAssignment(
            asset_id=asset.id,
            user_id=user.id,
            assigned_by=current_user.id,
            expected_return=expected_return,
            condition_out=condition,
        )
    )
    asset.status = "assigned"
    asset.assigned_to = user.id
    asset.condition = condition
    due = f", due back {expected_return:%d %b %Y}" if expected_return else ""
    notify(
        [user.id],
        f"{asset.name} ({asset.asset_code}) is now assigned to you{due}.",
        link="/assets",
        email_subject=f"{asset.name} assigned to you",
    )
    audit(
        "assigned",
        "asset",
        asset.id,
        f"Assigned to {user.full_name} (condition: {condition}{due})",
        {"status": ["available", "assigned"]},
    )


@blp.route("/", methods=["POST"])
@blp.arguments(AssetSchema)
@blp.response(201, AssetSchema)
@roles_required(*MANAGERS)
def create_asset(data):
    check_category(data["category_id"])
    holder_id = data.pop("assigned_to")
    expected_return = data.pop("expected_return")
    holder = active_user(holder_id) if holder_id else None
    asset = Asset(**data, status="available")
    db.session.add(asset)
    db.session.flush()
    audit("created", "asset", asset.id, f"{asset.asset_code} {asset.name} registered")
    if holder:
        open_assignment(asset, holder, data["condition"], expected_return)
    db.session.commit()
    return load(asset.id)


@blp.route("/<int:asset_id>")
@blp.response(200, AssetSchema)
@roles_required()
def get_asset(asset_id):
    visible(asset_id)
    return load(asset_id)


@blp.route("/<int:asset_id>", methods=["PUT"])
@blp.arguments(AssetSchema)
@blp.response(200, AssetSchema)
@roles_required(*MANAGERS)
def update_asset(data, asset_id):
    asset = get_or_404(Asset, asset_id)
    check_category(data["category_id"])
    data.pop("assigned_to")
    data.pop("expected_return")
    changes = diff(asset, data)
    for key, value in data.items():
        setattr(asset, key, value)
    if changes:
        audit("updated", "asset", asset.id, f"{asset.name} edited", changes)
    db.session.commit()
    return load(asset_id)


@blp.route("/<int:asset_id>", methods=["DELETE"])
@blp.response(204)
@roles_required(*MANAGERS)
def delete_asset(asset_id):
    asset = get_or_404(Asset, asset_id)
    if asset.assignments or asset.repairs:
        abort(409, message="This asset has history (assignments or repairs). Retire it instead.")
    delete(asset, "This asset has history and cannot be deleted.")


def locked(asset_id):
    asset = db.session.scalar(db.select(Asset).where(Asset.id == asset_id).with_for_update())
    if asset is None:
        abort(404, message=f"Asset {asset_id} not found")
    return asset


@blp.route("/<int:asset_id>/assign", methods=["POST"])
@blp.arguments(AssignIn)
@blp.response(200, AssetSchema)
@roles_required(*MANAGERS)
def assign(data, asset_id):
    asset = locked(asset_id)
    if asset.status != "available":
        db.session.rollback()
        abort(
            409,
            message=f"{asset.name} is {asset.status.replace('_', ' ')}; "
            "only available assets can be assigned.",
        )
    user = active_user(data["user_id"])
    open_assignment(asset, user, data["condition"], data["expected_return"])
    save(asset, f"{asset.name} already has an open assignment.")
    return load(asset_id)


@blp.route("/<int:asset_id>/return", methods=["POST"])
@blp.arguments(ReturnIn)
@blp.response(200, AssetSchema)
@roles_required(*MANAGERS)
def return_asset(data, asset_id):
    asset = locked(asset_id)
    assignment = db.session.scalar(
        db.select(AssetAssignment).where(
            AssetAssignment.asset_id == asset.id, AssetAssignment.returned_at.is_(None)
        )
    )
    if assignment is None:
        db.session.rollback()
        abort(409, message=f"{asset.name} is not assigned to anyone.")
    if asset.status == "in_repair":
        db.session.rollback()
        abort(409, message=f"{asset.name} is in repair; finish the repair first.")
    assignment.returned_at = datetime.now(UTC)
    assignment.received_by = current_user.id
    assignment.condition_in = data["condition"]
    assignment.return_notes = data["notes"]
    holder = db.session.get(User, assignment.user_id)
    asset.status = "available"
    asset.assigned_to = None
    asset.condition = data["condition"]
    audit(
        "returned",
        "asset",
        asset.id,
        f"Returned by {holder.full_name} (condition: {data['condition']})"
        + (f": {data['notes']}" if data["notes"] else ""),
        {"status": ["assigned", "available"]},
    )
    db.session.commit()
    return load(asset_id)


@blp.route("/<int:asset_id>/retire", methods=["POST"])
@blp.response(200, AssetSchema)
@roles_required(*MANAGERS)
def retire(asset_id):
    asset = locked(asset_id)
    if asset.status != "available":
        db.session.rollback()
        abort(409, message="Return the asset (and finish any repair) before retiring it.")
    asset.status = "retired"
    audit(
        "retired", "asset", asset.id, f"{asset.name} retired", {"status": ["available", "retired"]}
    )
    db.session.commit()
    return load(asset_id)


@blp.route("/<int:asset_id>/assignments")
@blp.arguments(PageQuery, location="query")
@blp.response(200, page_schema(AssignmentOut))
@roles_required()
def assignments(args, asset_id):
    visible(asset_id)
    query = (
        db.select(AssetAssignment)
        .options(
            selectinload(AssetAssignment.user),
            selectinload(AssetAssignment.assigner),
            selectinload(AssetAssignment.receiver),
        )
        .where(AssetAssignment.asset_id == asset_id)
        .order_by(AssetAssignment.assigned_at.desc(), AssetAssignment.id.desc())
    )
    return paginate(query, args["page"], args["per_page"])


@blp.route("/<int:asset_id>/timeline")
@blp.arguments(PageQuery, location="query")
@blp.response(200, page_schema(TimelineEntry))
@roles_required()
def timeline(args, asset_id):
    visible(asset_id)
    return record_timeline("asset", asset_id, args["page"], args["per_page"])


@blp.route("/<int:asset_id>/photo", methods=["POST"])
@blp.response(200, AssetSchema)
@roles_required(*MANAGERS)
def upload_photo(asset_id):
    asset = get_or_404(Asset, asset_id)
    replace_photo(asset, read_upload())
    db.session.commit()
    return load(asset_id)


@blp.route("/<int:asset_id>/photo", methods=["DELETE"])
@blp.response(200, AssetSchema)
@roles_required(*MANAGERS)
def delete_photo(asset_id):
    asset = get_or_404(Asset, asset_id)
    remove_photo(asset)
    db.session.commit()
    return load(asset_id)


@categories_blp.route("/")
@categories_blp.arguments(PageQuery, location="query")
@categories_blp.response(200, page_schema(AssetCategorySchema))
@roles_required()
def list_categories(args):
    query = db.select(AssetCategory).order_by(AssetCategory.name)
    return paginate(query, args["page"], args["per_page"])


@categories_blp.route("/", methods=["POST"])
@categories_blp.arguments(AssetCategorySchema)
@categories_blp.response(201, AssetCategorySchema)
@roles_required(*MANAGERS)
def create_category(data):
    return save(AssetCategory(**data), f"Asset category '{data['name']}' already exists")


@categories_blp.route("/<int:category_id>", methods=["PUT"])
@categories_blp.arguments(AssetCategorySchema)
@categories_blp.response(200, AssetCategorySchema)
@roles_required(*MANAGERS)
def update_category(data, category_id):
    category = get_or_404(AssetCategory, category_id, "Asset category")
    category.name = data["name"]
    return save(category, f"Asset category '{data['name']}' already exists")


@categories_blp.route("/<int:category_id>", methods=["DELETE"])
@categories_blp.response(204)
@roles_required(*MANAGERS)
def delete_category(category_id):
    category = get_or_404(AssetCategory, category_id, "Asset category")
    delete(category, "This category still has assets. Move them first.")


blueprints = [blp, categories_blp]
