"""Purchases recorded from scanned receipts

Revision ID: 3d7c2a91f0b4
Revises: c8b610b54ddf
Create Date: 2026-11-28 00:10:00.000000

"""

from alembic import op

revision = "3d7c2a91f0b4"
down_revision = "c8b610b54ddf"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(op.f("ck_purchases_source_valid"), "purchases", type_="check")
    op.create_check_constraint(
        op.f("ck_purchases_source_valid"),
        "purchases",
        "source IN ('manual', 'low_stock', 'request', 'receipt')",
    )


def downgrade():
    op.execute("UPDATE purchases SET source = 'manual' WHERE source = 'receipt'")
    op.drop_constraint(op.f("ck_purchases_source_valid"), "purchases", type_="check")
    op.create_check_constraint(
        op.f("ck_purchases_source_valid"),
        "purchases",
        "source IN ('manual', 'low_stock', 'request')",
    )
