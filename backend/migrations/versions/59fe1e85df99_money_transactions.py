import sqlalchemy as sa
from alembic import op

CATEGORIES = (
    "'sales', "
    "'loan', "
    "'owner_deposit', "
    "'other_income', "
    "'stock', "
    "'rent', "
    "'utilities', "
    "'wages', "
    "'transport', "
    "'airtime', "
    "'fees', "
    "'loan_repayment', "
    "'withdrawal', "
    "'personal', "
    "'other_expense'"
)

revision = "59fe1e85df99"
down_revision = "8a6f563bed31"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "category_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=3), nullable=False),
        sa.Column("match", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name=op.f("fk_category_rules_business_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_category_rules")),
        sa.UniqueConstraint("business_id", "direction", "match", name="uq_category_rules_match"),
    )
    with op.batch_alter_table("category_rules", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_category_rules_business_id"), ["business_id"], unique=False
        )

    op.create_table(
        "money_imports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=10), nullable=False),
        sa.Column("filename", sa.String(length=200), nullable=True),
        sa.Column("added", sa.Integer(), nullable=False),
        sa.Column("duplicates", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("first_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "source IN ('statement', 'csv', 'sms')", name=op.f("ck_money_imports_source_valid")
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name=op.f("fk_money_imports_business_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_money_imports_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_money_imports")),
    )
    with op.batch_alter_table("money_imports", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_money_imports_business_id"), ["business_id"], unique=False
        )

    op.create_table(
        "money_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_id", sa.Integer(), nullable=False),
        sa.Column("receipt", sa.String(length=20), nullable=False),
        sa.Column("is_charge", sa.Boolean(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("direction", sa.String(length=3), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("balance", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("counterparty", sa.String(length=120), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("details", sa.String(length=300), nullable=True),
        sa.Column("sale_id", sa.Integer(), nullable=True),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            f"category IN ({CATEGORIES})",
            name=op.f("ck_money_transactions_category_valid"),
        ),
        sa.CheckConstraint(
            "direction IN ('in', 'out')", name=op.f("ck_money_transactions_direction_valid")
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_money_transactions_amount_positive")),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name=op.f("fk_money_transactions_business_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["import_id"],
            ["money_imports.id"],
            name=op.f("fk_money_transactions_import_id_money_imports"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sale_id"],
            ["sales.id"],
            name=op.f("fk_money_transactions_sale_id_sales"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_money_transactions")),
        sa.UniqueConstraint(
            "business_id", "receipt", "is_charge", name="uq_money_transactions_receipt"
        ),
    )
    with op.batch_alter_table("money_transactions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_money_transactions_business_id"), ["business_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_money_transactions_occurred_at"), ["occurred_at"], unique=False
        )


def downgrade():
    with op.batch_alter_table("money_transactions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_money_transactions_occurred_at"))
        batch_op.drop_index(batch_op.f("ix_money_transactions_business_id"))

    op.drop_table("money_transactions")
    with op.batch_alter_table("money_imports", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_money_imports_business_id"))

    op.drop_table("money_imports")
    with op.batch_alter_table("category_rules", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_category_rules_business_id"))

    op.drop_table("category_rules")
