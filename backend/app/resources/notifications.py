from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import fields

from app.auth import roles_required
from app.crud import PageQuery, page_schema, paginate
from app.extensions import db
from app.models import Notification
from app.schemas import Schema

blp = Blueprint(
    "notifications", __name__, url_prefix="/api/notifications", description="Notifications"
)


class NotificationOut(Schema):
    id = fields.Integer()
    message = fields.String()
    link = fields.String(allow_none=True)
    is_read = fields.Boolean()
    created_at = fields.DateTime()


class NotificationQuery(PageQuery):
    unread = fields.Boolean(load_default=False)


class UpdatedOut(Schema):
    updated = fields.Integer()


def mine():
    return db.select(Notification).where(Notification.user_id == current_user.id)


@blp.route("/")
@blp.arguments(NotificationQuery, location="query")
@blp.response(200, page_schema(NotificationOut))
@roles_required()
def list_notifications(args):
    query = mine().order_by(Notification.created_at.desc(), Notification.id.desc())
    if args["unread"]:
        query = query.where(Notification.is_read.is_(False))
    return paginate(query, args["page"], args["per_page"])


@blp.route("/<int:notification_id>/read", methods=["POST"])
@blp.response(200, NotificationOut)
@roles_required()
def mark_read(notification_id):
    notification = db.session.scalar(mine().where(Notification.id == notification_id))
    if notification is None:
        abort(404, message=f"Notification {notification_id} not found")
    notification.is_read = True
    db.session.commit()
    return notification


@blp.route("/read-all", methods=["POST"])
@blp.response(200, UpdatedOut)
@roles_required()
def mark_all_read():
    result = db.session.execute(
        db.update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.session.commit()
    return {"updated": result.rowcount}
