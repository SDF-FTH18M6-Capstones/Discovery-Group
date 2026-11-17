from app.extensions import db
from app.models.base import TimestampMixin, in_list

ASSET_STATUSES = ("available", "assigned", "in_repair")
REPAIR_STATUSES = ("submitted", "in_progress", "done")


class Asset(TimestampMixin, db.Model):
    __tablename__ = "assets"
    __table_args__ = (in_list("status", ASSET_STATUSES, "status_valid"),)

    id = db.Column(db.Integer, primary_key=True)
    asset_code = db.Column(db.String(30), nullable=False, unique=True)  # also the barcode value
    name = db.Column(db.String(150), nullable=False, index=True)
    image_url = db.Column(db.String(500))
    status = db.Column(db.String(12), nullable=False, server_default="available", index=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), index=True)

    holder = db.relationship("User")
    repairs = db.relationship("Repair", back_populates="asset")


class Repair(TimestampMixin, db.Model):
    __tablename__ = "repairs"
    __table_args__ = (in_list("status", REPAIR_STATUSES, "status_valid"),)

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(
        db.Integer, db.ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    reported_by = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(12), nullable=False, server_default="submitted", index=True)

    asset = db.relationship("Asset", back_populates="repairs")
    reporter = db.relationship("User")


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, server_default=db.false())
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
