import re

from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    current_user,
    jwt_required,
)
from flask_smorest import Blueprint, abort
from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate, validates

from app.auth import roles_required
from app.extensions import db
from app.models import Employee, User
from app.models.user import check_secret, hash_secret

blp = Blueprint("auth", __name__, url_prefix="/api/auth", description="Sign-in and accounts")

BAD_LOGIN = "Email or password is incorrect."


class RegisterSchema(Schema):
    class Meta:
        unknown = EXCLUDE  

    full_name = fields.String(required=True, validate=validate.Length(min=2, max=120))
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)

    @validates("password")
    def strong_enough(self, value, **kwargs):
        if len(value) < 8 or not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise ValidationError("Use at least 8 characters with letters and numbers.")
        if len(value.encode("utf-8")) > 72:
            raise ValidationError("Use at most 72 characters.")


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)


class AccountSchema(Schema):
    id = fields.Integer()
    full_name = fields.String()
    email = fields.String()
    role = fields.String()


class MessageSchema(Schema):
    message = fields.String()


class SessionSchema(Schema):
    access_token = fields.String()
    refresh_token = fields.String()
    user = fields.Nested(AccountSchema)


class AccessSchema(Schema):
    access_token = fields.String()


# ---------- helpers ----------

_dummy = {}


def dummy_hash():
    """A real hash to check against when the email is unknown, so the answer takes as long
    as for a real account and nobody can tell which emails exist."""
    if "hash" not in _dummy:
        _dummy["hash"] = hash_secret("not-a-real-password-1")
    return _dummy["hash"]


def find_user(email):
    return db.session.scalar(db.select(User).filter_by(email=email.lower()))



@blp.route("/register", methods=["POST"])
@blp.arguments(RegisterSchema)
@blp.response(201, MessageSchema)
@blp.doc(security=[])
def register(data):
    """Create an account. Every new account is an Employee, whatever the request says."""
    if find_user(data["email"]):
        abort(409, message="An account with this email already exists.")
    user = Employee(full_name=data["full_name"], email=data["email"].lower())
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    return {"message": "Account created. You can now sign in."}


@blp.route("/login", methods=["POST"])
@blp.arguments(LoginSchema)
@blp.response(200, SessionSchema)
@blp.doc(security=[])
def login(data):
  
    user = find_user(data["email"])
    if user is None:
        check_secret(dummy_hash(), data["password"])  # same delay as a real check
        abort(401, message=BAD_LOGIN)
    if not user.check_password(data["password"]):
        abort(401, message=BAD_LOGIN)
    return {
        "access_token": create_access_token(identity=user, additional_claims={"role": user.role}),
        "refresh_token": create_refresh_token(identity=user),
        "user": user,
    }


@blp.route("/refresh", methods=["POST"])
@blp.response(200, AccessSchema)
@jwt_required(refresh=True)
def refresh():
  
    token = create_access_token(
        identity=current_user, additional_claims={"role": current_user.role}
    )
    return {"access_token": token}


@blp.route("/me")
@blp.response(200, AccountSchema)
@roles_required()
def me():
    return current_user