"""M-Pesa messages from a linked phone, and WhatsApp alerts

Revision ID: bfaaf36901e9
Revises: 3d7c2a91f0b4
Create Date: 2026-11-28 00:29:33.637419

"""

import sqlalchemy as sa
from alembic import op

revision = "bfaaf36901e9"
down_revision = "3d7c2a91f0b4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "phone_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("messages", sa.Integer(), server_default="0", nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name=op.f("fk_phone_links_business_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_phone_links_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_phone_links")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_phone_links_token_hash")),
    )
    op.create_index(op.f("ix_phone_links_business_id"), "phone_links", ["business_id"])
    with op.batch_alter_table("businesses") as batch_op:
        batch_op.add_column(sa.Column("whatsapp_number", sa.String(length=20), nullable=True))
        batch_op.add_column(
            sa.Column(
                "whatsapp_alerts", sa.Boolean(), server_default=sa.text("false"), nullable=False
            )
        )
    with op.batch_alter_table("money_imports") as batch_op:
        batch_op.drop_constraint("source_valid", type_="check")
        batch_op.create_check_constraint(
            "source_valid", "source IN ('statement', 'csv', 'sms', 'phone')"
        )


def downgrade():
    op.execute("DELETE FROM money_imports WHERE source = 'phone'")
    with op.batch_alter_table("money_imports") as batch_op:
        batch_op.drop_constraint("source_valid", type_="check")
        batch_op.create_check_constraint("source_valid", "source IN ('statement', 'csv', 'sms')")
    with op.batch_alter_table("businesses") as batch_op:
        batch_op.drop_column("whatsapp_alerts")
        batch_op.drop_column("whatsapp_number")
    op.drop_index(op.f("ix_phone_links_business_id"), table_name="phone_links")
    op.drop_table("phone_links")
