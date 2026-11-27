import sqlalchemy as sa
from alembic import op

revision = "124577034daa"
down_revision = "e5f1e5474e06"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mpesa_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("attendant_id", sa.Integer(), nullable=False),
        sa.Column("phone", sa.String(length=15), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=12), server_default="pending", nullable=False),
        sa.Column("simulated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("checkout_request_id", sa.String(length=80), nullable=True),
        sa.Column("merchant_request_id", sa.String(length=80), nullable=True),
        sa.Column("receipt_number", sa.String(length=20), nullable=True),
        sa.Column("result_code", sa.Integer(), nullable=True),
        sa.Column("result_desc", sa.String(length=255), nullable=True),
        sa.Column("problem", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
        sa.Column("sale_id", sa.Integer(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'paid', 'failed', 'cancelled')",
            name=op.f("ck_mpesa_payments_status_valid"),
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_mpesa_payments_amount_positive")),
        sa.ForeignKeyConstraint(
            ["attendant_id"],
            ["users.id"],
            name=op.f("fk_mpesa_payments_attendant_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name=op.f("fk_mpesa_payments_business_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sale_id"],
            ["sales.id"],
            name=op.f("fk_mpesa_payments_sale_id_sales"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mpesa_payments")),
        sa.UniqueConstraint(
            "business_id", "idempotency_key", name="uq_mpesa_payments_idempotency_key"
        ),
        sa.UniqueConstraint(
            "checkout_request_id", name=op.f("uq_mpesa_payments_checkout_request_id")
        ),
        sa.UniqueConstraint("receipt_number", name=op.f("uq_mpesa_payments_receipt_number")),
    )
    with op.batch_alter_table("mpesa_payments", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_mpesa_payments_attendant_id"), ["attendant_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_mpesa_payments_business_id"), ["business_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_mpesa_payments_created_at"), ["created_at"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_mpesa_payments_sale_id"), ["sale_id"], unique=False)

    with op.batch_alter_table("businesses", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("daily_summary", sa.Boolean(), server_default=sa.text("true"), nullable=False)
        )
        batch_op.add_column(sa.Column("summary_sent_on", sa.Date(), nullable=True))

    with op.batch_alter_table("sales", schema=None) as batch_op:
        batch_op.add_column(sa.Column("payment_reference", sa.String(length=30), nullable=True))


def downgrade():
    with op.batch_alter_table("sales", schema=None) as batch_op:
        batch_op.drop_column("payment_reference")

    with op.batch_alter_table("businesses", schema=None) as batch_op:
        batch_op.drop_column("summary_sent_on")
        batch_op.drop_column("daily_summary")

    with op.batch_alter_table("mpesa_payments", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_mpesa_payments_sale_id"))
        batch_op.drop_index(batch_op.f("ix_mpesa_payments_created_at"))
        batch_op.drop_index(batch_op.f("ix_mpesa_payments_business_id"))
        batch_op.drop_index(batch_op.f("ix_mpesa_payments_attendant_id"))

    op.drop_table("mpesa_payments")
