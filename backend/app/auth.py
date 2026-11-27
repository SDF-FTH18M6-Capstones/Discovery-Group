from functools import wraps

from flask import g, jsonify
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_smorest import abort

from app.extensions import db, jwt
from app.models import RevokedToken, User
from app.tenancy import clear_business, set_business, tenant

ALL_ROLES = ("admin", "procurement", "inventory", "sales", "employee")
JOB_ROLES = ("procurement", "inventory", "sales")
JOB_NAMES = {"procurement": "Procurement", "inventory": "Inventory", "sales": "Sales"}


def unstaffed_roles(business_id):
    with tenant(business_id):
        staffed = set(
            db.session.scalars(
                db.select(User.role)
                .where(
                    User.role.in_(JOB_ROLES),
                    User.is_active.is_(True),
                    User.approved_at.is_not(None),
                )
                .distinct()
            )
        )
    return [role for role in JOB_ROLES if role not in staffed]


def covered_roles():
    if "covered_roles" not in g:
        g.covered_roles = unstaffed_roles(current_user.business_id)
    return g.covered_roles


def covers_for(user):
    return unstaffed_roles(user.business_id) if user.role == "admin" else []


def can(*roles):
    if current_user.role in roles:
        return True
    return current_user.role == "admin" and any(r in covered_roles() for r in roles)


def roles_required(*roles):
    allowed = roles or ALL_ROLES

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            if not can(*allowed):
                if current_user.role == "admin":
                    staff = " or ".join(JOB_NAMES[r] for r in allowed if r in JOB_NAMES)
                    abort(
                        403,
                        message=f"Your {staff} staff handle this. As Administrator you can "
                        "follow it, but not do it.",
                    )
                abort(403, message="You do not have permission to do this.")
            return view(*args, **kwargs)

        return wrapper

    return decorator


def is_role(*roles) -> bool:
    return current_user.role in roles


def error(code, message):
    return jsonify(error={"code": code, "message": message}), code


@jwt.user_identity_loader
def user_identity(user):
    return str(user.id)


@jwt.user_lookup_loader
def load_user(_header, payload):
    clear_business()
    user = db.session.get(User, int(payload["sub"]))
    if user is None or not user.is_active or not user.business.is_active:
        return None
    if user.approved_at is None:
        return None
    set_business(user.business_id)
    return user


@jwt.token_in_blocklist_loader
def token_revoked(_header, payload):
    clear_business()
    session_ids = [jti for jti in (payload.get("jti"), payload.get("sid")) if jti]
    if session_ids and db.session.scalar(
        db.select(RevokedToken.jti).where(RevokedToken.jti.in_(session_ids)).limit(1)
    ):
        return True
    user = db.session.get(User, int(payload["sub"]))
    return user is not None and payload.get("sv", 0) != user.session_version


@jwt.user_lookup_error_loader
def user_gone(_header, payload):
    user = db.session.get(User, int(payload["sub"]))
    if user is not None and not user.is_active:
        return error(401, "This account has been deactivated. Ask your administrator.")
    return error(401, "Your account no longer exists. Please sign in again.")


@jwt.unauthorized_loader
def missing_token(_reason):
    return error(401, "Please sign in to continue.")


@jwt.invalid_token_loader
def bad_token(_reason):
    return error(401, "Your session is not valid. Please sign in again.")


@jwt.expired_token_loader
def expired_token(_header, _payload):
    return error(401, "Your session has expired. Please sign in again.")


@jwt.needs_fresh_token_loader
def stale_token(_header, _payload):
    return error(401, "Please sign in again.")


@jwt.revoked_token_loader
def revoked_token(_header, _payload):
    return error(401, "Your session has ended. Please sign in again.")
