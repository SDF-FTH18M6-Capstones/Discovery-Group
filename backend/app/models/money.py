from app.extensions import db
from app.models.base import Money, TenantMixin, in_list

MONEY_IN = ("sales", "loan", "owner_deposit", "savings", "other_income")
MONEY_OUT = (
    "stock",
    "rent",
    "utilities",
    "wages",
    "transport",
    "airtime",
    "fees",
    "loan_repayment",
    "withdrawal",
    "savings",
    "personal",
    "other_expense",
)
TRANSFERS = ("owner_deposit", "withdrawal", "savings")
CATEGORIES = tuple(dict.fromkeys(MONEY_IN + MONEY_OUT))


class MoneyImport(TenantMixin, db.Model):
    __tablename__ = "money_imports"
    __table_args__ = (in_list("source", ("statement", "csv", "sms"), "source_valid"),)

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(10), nullable=False)
    filename = db.Column(db.String(200))
    added = db.Column(db.Integer, nullable=False, default=0)
    duplicates = db.Column(db.Integer, nullable=False, default=0)
    skipped = db.Column(db.Integer, nullable=False, default=0)
    first_at = db.Column(db.DateTime(timezone=True))
    last_at = db.Column(db.DateTime(timezone=True))
    created_by = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    transactions = db.relationship(
        "MoneyTransaction", back_populates="source_import", cascade="all, delete-orphan"
    )


class MoneyTransaction(TenantMixin, db.Model):
    __tablename__ = "money_transactions"
    __table_args__ = (
        db.UniqueConstraint(
            "business_id",
            "receipt",
            "is_charge",
            "direction",
            "amount",
            name="uq_money_transactions_receipt",
        ),
        db.CheckConstraint("amount > 0", name="amount_positive"),
        in_list("direction", ("in", "out"), "direction_valid"),
        in_list("category", CATEGORIES, "category_valid"),
    )

    id = db.Column(db.Integer, primary_key=True)
    import_id = db.Column(
        db.Integer, db.ForeignKey("money_imports.id", ondelete="CASCADE"), nullable=False
    )
    receipt = db.Column(db.String(20), nullable=False)
    is_charge = db.Column(db.Boolean, nullable=False, default=False)
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    direction = db.Column(db.String(3), nullable=False)
    amount = db.Column(Money, nullable=False)
    balance = db.Column(Money)
    kind = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(20), nullable=False)
    counterparty = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    details = db.Column(db.String(300))
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id", ondelete="SET NULL"))

    source_import = db.relationship("MoneyImport", back_populates="transactions")


class CategoryRule(TenantMixin, db.Model):
    __tablename__ = "category_rules"
    __table_args__ = (
        db.UniqueConstraint("business_id", "direction", "match", name="uq_category_rules_match"),
    )

    id = db.Column(db.Integer, primary_key=True)
    direction = db.Column(db.String(3), nullable=False)
    match = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(20), nullable=False)
