from app.extensions import bcrypt, db
from app.models.base import TimestampMixin, in_list

ROLES = ("admin", "procurement", "inventory", "sales", "employee")


def hash_secret(raw: str) -> str:
    """Bcrypt hash for passwords and sign-in codes."""
    return bcrypt.generate_password_hash(raw).decode("utf-8")


def check_secret(hashed: str | None, raw: str) -> bool:
    # Bcrypt only reads the first 72 bytes; longer input is refused outright.
    if not hashed or len(raw.encode("utf-8")) > 72:
        return False
    try:
        return bcrypt.check_password_hash(hashed, raw)
    except ValueError:  # not a bcrypt hash (e.g. saved before the switch to bcrypt)
        return False


class User(TimestampMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (in_list("role", ROLES, "role_valid"),)

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, index=True)
    is_verified = db.Column(db.Boolean, nullable=False, server_default=db.false())
    otp_hash = db.Column(db.String(255))  # 2-step sign-in code, stored hashed, never plain
    otp_expires_at = db.Column(db.DateTime(timezone=True))
    otp_attempts = db.Column(db.Integer, nullable=False, server_default="0")

    __mapper_args__ = {"polymorphic_on": role, "polymorphic_identity": "user"}

    # Permissions — each role class switches on what it may do.
    can_manage_users = False
    can_approve_requests = False
    can_manage_purchases = False
    can_manage_stock = False
    can_make_sales = False
    can_manage_assets = False

    def set_password(self, raw_password: str) -> None:
        self.password_hash = hash_secret(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_secret(self.password_hash, raw_password)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.email}>"


class Admin(User):
    __mapper_args__ = {"polymorphic_identity": "admin"}
    can_manage_users = True
    can_manage_stock = True
    can_manage_assets = True
    # Not can_approve_requests: only the Procurement Manager approves.


class ProcurementManager(User):
    __mapper_args__ = {"polymorphic_identity": "procurement"}
    can_approve_requests = True
    can_manage_purchases = True


class InventoryManager(User):
    __mapper_args__ = {"polymorphic_identity": "inventory"}
    can_manage_stock = True
    can_manage_assets = True


class SalesAttendant(User):
    __mapper_args__ = {"polymorphic_identity": "sales"}
    can_make_sales = True


class Employee(User):
    """Default role for every self-registered account."""

    __mapper_args__ = {"polymorphic_identity": "employee"}


ROLE_CLASSES = {
    "admin": Admin,
    "procurement": ProcurementManager,
    "inventory": InventoryManager,
    "sales": SalesAttendant,
    "employee": Employee,
}