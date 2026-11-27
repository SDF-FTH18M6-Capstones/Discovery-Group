import sqlalchemy as sa
from alembic import op

revision = "e5f1e5474e06"
down_revision = "e78b2640daec"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE users SET approved_at = created_at")

    with op.batch_alter_table("products") as batch_op:
        batch_op.add_column(sa.Column("reorder_quantity", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("default_supplier_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_products_default_supplier_id"), ["default_supplier_id"], unique=False
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_products_default_supplier_id_suppliers"),
            "suppliers",
            ["default_supplier_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_check_constraint(
        op.f("ck_products_reorder_quantity_positive"), "products", "reorder_quantity > 0"
    )

    with op.batch_alter_table("purchases") as batch_op:
        batch_op.add_column(
            sa.Column("source", sa.String(length=12), server_default="manual", nullable=False)
        )
    op.create_check_constraint(
        op.f("ck_purchases_source_valid"),
        "purchases",
        "source IN ('manual', 'low_stock', 'request')",
    )


def downgrade():
    op.drop_constraint(op.f("ck_purchases_source_valid"), "purchases", type_="check")
    with op.batch_alter_table("purchases") as batch_op:
        batch_op.drop_column("source")

    op.drop_constraint(op.f("ck_products_reorder_quantity_positive"), "products", type_="check")
    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_products_default_supplier_id_suppliers"), type_="foreignkey"
        )
        batch_op.drop_index(batch_op.f("ix_products_default_supplier_id"))
        batch_op.drop_column("default_supplier_id")
        batch_op.drop_column("reorder_quantity")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("approved_at")
