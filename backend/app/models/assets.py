from app.extensions import db
from app.models.base import Money, TenantMixin, TimestampMixin, in_list, reference

ASSET_STATUSES = ("available", "assigned", "in_repair", "retired")
CONDITIONS = ("new", "good", "fair", "poor", "damaged")
REPAIR_STATUSES = ("submitted", "in_progress", "done", "rejected")
OPEN_REPAIR_STATUSES = ("submitted", "in_progress")
REPAIR_URGENCIES = ("low", "normal", "high", "urgent")


class AssetCategory(TenantMixin, TimestampMixin, db.Model):
    __tablename__ = "asset_categories"
    __table_args__ = (db.UniqueConstraint("business_id", "name", name="uq_asset_categories_name"),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)


class Asset(TenantMixin, TimestampMixin, db.Model):
    __tablename__ = "assets"
    __number_kind__ = "asset"
    __table_args__ = (
        db.UniqueConstraint("business_id", "number", name="uq_assets_number"),
        db.UniqueConstraint("business_id", "asset_code", name="uq_assets_asset_code"),
        db.UniqueConstraint("business_id", "barcode", name="uq_assets_barcode"),
        in_list("status", ASSET_STATUSES, "status_valid"),
        in_list("condition", CONDITIONS, "condition_valid"),
    )

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, nullable=False)
    asset_code = db.Column(db.String(30), nullable=False)
    barcode = db.Column(db.String(40), nullable=False)
    name = db.Column(db.String(150), nullable=False, index=True)
    category_id = db.Column(
        db.Integer, db.ForeignKey("asset_categories.id", ondelete="RESTRICT"), index=True
    )
    serial_number = db.Column(db.String(100))
    purchase_date = db.Column(db.Date)
    purchase_cost = db.Column(Money)
    condition = db.Column(db.String(10), nullable=False, server_default="good", default="good")
    notes = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    image_id = db.Column(db.String(36), db.ForeignKey("images.id", ondelete="SET NULL"))
    status = db.Column(db.String(12), nullable=False, server_default="available", index=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), index=True)

    holder = db.relationship("User")
    category = db.relationship("AssetCategory")
    repairs = db.relationship("Repair", back_populates="asset")
    assignments = db.relationship(
        "AssetAssignment",
        back_populates="asset",
        order_by="AssetAssignment.assigned_at.desc()",
    )
    current_assignment = db.relationship(
        "AssetAssignment",
        primaryjoin="and_(AssetAssignment.asset_id == Asset.id, "
        "AssetAssignment.returned_at.is_(None))",
        uselist=False,
        viewonly=True,
    )
    open_repair = db.relationship(
        "Repair",
        primaryjoin="and_(Repair.asset_id == Asset.id, "
        "Repair.status.in_(('submitted', 'in_progress')))",
        uselist=False,
        viewonly=True,
    )


class AssetAssignment(TenantMixin, db.Model):
    __tablename__ = "asset_assignments"
    __table_args__ = (
        in_list("condition_out", CONDITIONS, "condition_out_valid"),
        db.CheckConstraint(
            "condition_in IS NULL OR condition_in IN ('new', 'good', 'fair', 'poor', 'damaged')",
            name="condition_in_valid",
        ),
        db.Index(
            "uq_asset_assignments_open",
            "asset_id",
            unique=True,
            postgresql_where=db.text("returned_at IS NULL"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(
        db.Integer, db.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    assigned_by = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    assigned_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )
    expected_return = db.Column(db.Date)
    condition_out = db.Column(db.String(10), nullable=False)
    returned_at = db.Column(db.DateTime(timezone=True))
    received_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"))
    condition_in = db.Column(db.String(10))
    return_notes = db.Column(db.Text)

    asset = db.relationship("Asset", back_populates="assignments")
    user = db.relationship("User", foreign_keys=[user_id])
    assigner = db.relationship("User", foreign_keys=[assigned_by])
    receiver = db.relationship("User", foreign_keys=[received_by])


class Repair(TenantMixin, TimestampMixin, db.Model):
    __tablename__ = "repairs"
    __number_kind__ = "repair"
    __table_args__ = (
        db.UniqueConstraint("business_id", "number", name="uq_repairs_number"),
        in_list("status", REPAIR_STATUSES, "status_valid"),
        in_list("urgency", REPAIR_URGENCIES, "urgency_valid"),
        db.CheckConstraint("cost IS NULL OR cost >= 0", name="cost_not_negative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, nullable=False)
    asset_id = db.Column(
        db.Integer, db.ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    reported_by = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    description = db.Column(db.Text, nullable=False)
    urgency = db.Column(db.String(10), nullable=False, server_default="normal", default="normal")
    status = db.Column(db.String(12), nullable=False, server_default="submitted", index=True)
    asset_status_before = db.Column(db.String(12))
    resolution = db.Column(db.Text)
    cost = db.Column(Money)
    started_at = db.Column(db.DateTime(timezone=True))
    closed_at = db.Column(db.DateTime(timezone=True))
    handled_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"))

    asset = db.relationship("Asset", back_populates="repairs")
    reporter = db.relationship("User", foreign_keys=[reported_by])
    handler = db.relationship("User", foreign_keys=[handled_by])

    @property
    def reference(self):
        return reference("REP", self.number, 3)


class Notification(TenantMixin, db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(200))
    is_read = db.Column(db.Boolean, nullable=False, server_default=db.false())
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
