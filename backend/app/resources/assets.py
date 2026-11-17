from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import ValidationError, fields, validate, validates_schema
from sqlalchemy.orm import selectinload

from app.auth import is_role, roles_required
from app.crud import PageQuery, delete, get_or_404, page_schema, paginate, save
from app.extensions import db
from app.models import Asset, User
from app.models.assets import ASSET_STATUSES
from app.schemas import Schema

MANAGERS = ("admin", "inventory")

blp = Blueprint("assets", __name__, url_prefix="/api/assets", description="Assets")


class AssetSchema(Schema):
    id = fields.Integer(dump_only=True)
    asset_code = fields.String(required=True, validate=validate.Length(min=1, max=30))
    name = fields.String(required=True, validate=validate.Length(min=1, max=150))
    image_url = fields.Url(allow_none=True, load_default=None)
    status = fields.String(load_default="available", validate=validate.OneOf(ASSET_STATUSES))
    assigned_to = fields.Integer(allow_none=True, load_default=None)
    holder_name = fields.String(attribute="holder.full_name", dump_only=True)

    @validates_schema
    def holder_matches_status(self, data, **kwargs):
        if data.get("status") == "assigned" and not data.get("assigned_to"):
            raise ValidationError("An assigned asset needs assigned_to.", "assigned_to")
        if data.get("status") == "available" and data.get("assigned_to"):
            raise ValidationError("An available asset cannot have a holder.", "assigned_to")


class AssetQuery(PageQuery):
    search = fields.String(load_default=None)
    status = fields.String(load_default=None, validate=validate.OneOf(ASSET_STATUSES))


def check_holder(user_id):
    if user_id is not None and db.session.get(User, user_id) is None:
        abort(400, message=f"User {user_id} does not exist")


@blp.route("/")
@blp.arguments(AssetQuery, location="query")
@blp.response(200, page_schema(AssetSchema))
@roles_required()
def list_assets(args):
    query = db.select(Asset).options(selectinload(Asset.holder)).order_by(Asset.asset_code)
    if not is_role(*MANAGERS):
        query = query.where(Asset.assigned_to == current_user.id)
    if args["search"]:
        term = f"%{args['search']}%"
        query = query.where(Asset.name.ilike(term) | Asset.asset_code.ilike(term))
    if args["status"]:
        query = query.where(Asset.status == args["status"])
    return paginate(query, args["page"], args["per_page"])


@blp.route("/", methods=["POST"])
@blp.arguments(AssetSchema)
@blp.response(201, AssetSchema)
@roles_required(*MANAGERS)
def create_asset(data):
    check_holder(data["assigned_to"])
    return save(Asset(**data), f"Asset code '{data['asset_code']}' is already used")


@blp.route("/<int:asset_id>")
@blp.response(200, AssetSchema)
@roles_required()
def get_asset(asset_id):
    asset = get_or_404(Asset, asset_id)
    if not is_role(*MANAGERS) and asset.assigned_to != current_user.id:
        abort(404, message=f"Asset {asset_id} not found")
    return asset


@blp.route("/<int:asset_id>", methods=["PUT"])
@blp.arguments(AssetSchema)
@blp.response(200, AssetSchema)
@roles_required(*MANAGERS)
def update_asset(data, asset_id):
    asset = get_or_404(Asset, asset_id)
    check_holder(data["assigned_to"])
    for key, value in data.items():
        setattr(asset, key, value)
    return save(asset, f"Asset code '{data['asset_code']}' is already used")


@blp.route("/<int:asset_id>", methods=["DELETE"])
@blp.response(204)
@roles_required(*MANAGERS)
def delete_asset(asset_id):
    asset = get_or_404(Asset, asset_id)
    delete(asset, "This asset has repair records and cannot be deleted.")
