from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import fields, validate

from app.audit import audit
from app.auth import roles_required
from app.crud import PageQuery, get_or_404, page_schema, paginate
from app.extensions import db
from app.models import User
from app.models.user import ROLES
from app.notify import notify
from app.schemas import Schema

ROLE_LABELS = {
    "admin": "Administrator",
    "procurement": "Procurement Manager",
    "inventory": "Inventory Manager",
    "sales": "Sales Attendant",
    "employee": "Employee",
}

blp = Blueprint("users", __name__, url_prefix="/api/users", description="Users (Administrator)")


class UserSchema(Schema):
    id = fields.Integer(dump_only=True)
    full_name = fields.String(dump_only=True)
    email = fields.String(dump_only=True)
    phone = fields.String(dump_only=True)
    role = fields.String(dump_only=True)
    is_active = fields.Boolean(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class ChoiceSchema(Schema):
    id = fields.Integer()
    full_name = fields.String()
    role = fields.String()


class RoleSchema(Schema):
    role = fields.String(required=True, validate=validate.OneOf(ROLES))


class UserQuery(PageQuery):
    search = fields.String(load_default=None)
    role = fields.String(load_default=None, validate=validate.OneOf(ROLES))
    active = fields.Boolean(load_default=None)


@blp.route("/")
@blp.arguments(UserQuery, location="query")
@blp.response(200, page_schema(UserSchema))
@roles_required("admin")
def list_users(args):
    query = db.select(User).order_by(User.full_name)
    if args["search"]:
        term = f"%{args['search']}%"
        query = query.where(User.full_name.ilike(term) | User.email.ilike(term))
    if args["role"]:
        query = query.where(User.role == args["role"])
    if args["active"] is not None:
        query = query.where(User.is_active.is_(args["active"]))
    return paginate(query, args["page"], args["per_page"])


@blp.route("/choices")
@blp.response(200, ChoiceSchema(many=True))
@roles_required("admin", "inventory")
def user_choices():
    return db.session.scalars(
        db.select(User).where(User.is_active.is_(True)).order_by(User.full_name)
    ).all()


@blp.route("/<int:user_id>")
@blp.response(200, UserSchema)
@roles_required("admin")
def get_user(user_id):
    return get_or_404(User, user_id)


@blp.route("/<int:user_id>/role", methods=["PUT"])
@blp.arguments(RoleSchema)
@blp.response(200, UserSchema)
@roles_required("admin")
def change_role(data, user_id):
    user = get_or_404(User, user_id)
    if user_id == current_user.id:
        abort(409, message="You cannot change your own role.")
    old_role = user.role
    if old_role == data["role"]:
        return user
    db.session.execute(db.update(User).where(User.id == user_id).values(role=data["role"]))
    notify([user_id], f"Your role is now {ROLE_LABELS[data['role']]}.")
    audit(
        "role_changed",
        "user",
        user_id,
        f"{user.full_name}: {ROLE_LABELS[old_role]} → {ROLE_LABELS[data['role']]}",
        {"role": [old_role, data["role"]]},
    )
    db.session.commit()
    db.session.expunge(user)
    return db.session.get(User, user_id)


def set_active(user_id, active):
    user = get_or_404(User, user_id)
    if user_id == current_user.id:
        abort(409, message="You cannot deactivate your own account.")
    if user.is_active == active:
        return user
    user.is_active = active
    word = "reactivated" if active else "deactivated"
    audit(word, "user", user.id, f"{user.full_name} {word}", {"is_active": [not active, active]})
    db.session.commit()
    return user


@blp.route("/<int:user_id>/deactivate", methods=["POST"])
@blp.response(200, UserSchema)
@roles_required("admin")
def deactivate(user_id):
    return set_active(user_id, False)


@blp.route("/<int:user_id>/reactivate", methods=["POST"])
@blp.response(200, UserSchema)
@roles_required("admin")
def reactivate(user_id):
    return set_active(user_id, True)
