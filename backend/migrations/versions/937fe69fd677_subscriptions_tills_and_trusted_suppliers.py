import sqlalchemy as sa
from alembic import op

revision = "937fe69fd677"
down_revision = "124577034daa"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("businesses") as batch_op:
        batch_op.add_column(sa.Column("trial_ends_on", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("paid_until", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("mpesa_mode", sa.String(length=10), nullable=True))
        batch_op.add_column(
            sa.Column("mpesa_type", sa.String(length=10), server_default="paybill", nullable=False)
        )
        batch_op.add_column(sa.Column("mpesa_shortcode", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("mpesa_till", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("mpesa_passkey", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("mpesa_consumer_key", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("mpesa_consumer_secret", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_businesses_mpesa_type_valid"), "businesses", "mpesa_type IN ('paybill', 'till')"
    )
    op.execute("UPDATE businesses SET trial_ends_on = CURRENT_DATE + 14")

    with op.batch_alter_table("mpesa_payments") as batch_op:
        batch_op.add_column(
            sa.Column("purpose", sa.String(length=12), server_default="sale", nullable=False)
        )
        batch_op.add_column(sa.Column("months", sa.Integer(), nullable=True))
    op.create_check_constraint(
        op.f("ck_mpesa_payments_purpose_valid"),
        "mpesa_payments",
        "purpose IN ('sale', 'subscription')",
    )

    with op.batch_alter_table("suppliers") as batch_op:
        batch_op.add_column(
            sa.Column("trusted", sa.Boolean(), server_default=sa.text("false"), nullable=False)
        )


def downgrade():
    with op.batch_alter_table("suppliers") as batch_op:
        batch_op.drop_column("trusted")

    op.drop_constraint(op.f("ck_mpesa_payments_purpose_valid"), "mpesa_payments", type_="check")
    with op.batch_alter_table("mpesa_payments") as batch_op:
        batch_op.drop_column("months")
        batch_op.drop_column("purpose")

    op.drop_constraint(op.f("ck_businesses_mpesa_type_valid"), "businesses", type_="check")
    with op.batch_alter_table("businesses") as batch_op:
        for column in (
            "mpesa_consumer_secret",
            "mpesa_consumer_key",
            "mpesa_passkey",
            "mpesa_till",
            "mpesa_shortcode",
            "mpesa_type",
            "mpesa_mode",
            "paid_until",
            "trial_ends_on",
        ):
            batch_op.drop_column(column)
