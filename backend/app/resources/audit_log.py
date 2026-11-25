from flask_smorest import Blueprint
from marshmallow import fields
from sqlalchemy.orm import selectinload

from app.auth import roles_required
from app.crud import PageQuery, page_schema, paginate
from app.extensions import db
from app.models import AuditLog
from app.schemas import Schema

blp = Blueprint("audit", __name__, url_prefix="/api/audit", description="Audit log (Admin)")


class AuditOut(Schema):
    id = fields.Integer()
    action = fields.String()
    entity_type = fields.String()
    entity_id = fields.Integer()
    summary = fields.String()
    changes = fields.Raw(allow_none=True)
    user_name = fields.String(attribute="user.full_name", allow_none=True)
    created_at = fields.DateTime()


class AuditQuery(PageQuery):
    entity_type = fields.String(load_default=None)
    entity_id = fields.Integer(load_default=None)
    action = fields.String(load_default=None)


@blp.route("/")
@blp.arguments(AuditQuery, location="query")
@blp.response(200, page_schema(AuditOut))
@roles_required("admin")
def list_audit(args):
    query = (
        db.select(AuditLog)
        .options(selectinload(AuditLog.user))
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    )
    for key in ("entity_type", "entity_id", "action"):
        if args[key] is not None:
            query = query.where(getattr(AuditLog, key) == args[key])
    return paginate(query, args["page"], args["per_page"])
