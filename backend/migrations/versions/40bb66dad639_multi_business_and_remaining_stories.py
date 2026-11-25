import secrets

import sqlalchemy as sa
from alembic import op

revision = "40bb66dad639"
down_revision = "9752b64b2612"
branch_labels = None
depends_on = None

TENANT_TABLES = [
    "users",
    "categories",
    "products",
    "suppliers",
    "requests",
    "purchases",
    "purchase_items",
    "sales",
    "sale_items",
    "stock_movements",
    "assets",
    "repairs",
    "notifications",
]
NUMBERED = {
    "suppliers": "supplier",
    "requests": "request",
    "purchases": "purchase",
    "sales": "sale",
    "assets": "asset",
    "repairs": "repair",
}


def add_business_id(table, business_id):
    op.add_column(table, sa.Column("business_id", sa.Integer(), nullable=True))
    op.execute(f"UPDATE {table} SET business_id = {business_id}")
    op.alter_column(table, "business_id", nullable=False)
    op.create_index(f"ix_{table}_business_id", table, ["business_id"])
    op.create_foreign_key(
        f"fk_{table}_business_id_businesses",
        table,
        "businesses",
        ["business_id"],
        ["id"],
        ondelete="CASCADE",
    )


def add_number(table, kind, business_id):
    op.add_column(table, sa.Column("number", sa.Integer(), nullable=True))
    op.execute(
        f"""UPDATE {table} t SET number = n.rn
            FROM (SELECT id, ROW_NUMBER() OVER (PARTITION BY business_id ORDER BY id) AS rn
                  FROM {table}) n
            WHERE t.id = n.id"""
    )
    op.alter_column(table, "number", nullable=False)
    op.create_unique_constraint(f"uq_{table}_number", table, ["business_id", "number"])
    op.execute(
        f"""INSERT INTO document_counters (business_id, kind, last)
            SELECT business_id, '{kind}', MAX(number) FROM {table} GROUP BY business_id"""
    )


def replace_check(table, name, condition):
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def upgrade():
    op.create_table(
        "businesses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("join_code", sa.String(length=12), nullable=False),
        sa.Column(
            "timezone", sa.String(length=64), server_default="Africa/Nairobi", nullable=False
        ),
        sa.Column("currency", sa.String(length=3), server_default="KES", nullable=False),
        sa.Column(
            "vat_rate", sa.Numeric(precision=5, scale=2), server_default="16", nullable=False
        ),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("address", sa.String(length=300), nullable=True),
        sa.Column("receipt_footer", sa.String(length=300), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "vat_rate >= 0 AND vat_rate < 100", name=op.f("ck_businesses_vat_rate_valid")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_businesses")),
        sa.UniqueConstraint("join_code", name=op.f("uq_businesses_join_code")),
    )
    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("jti", name=op.f("pk_revoked_tokens")),
    )
    with op.batch_alter_table("revoked_tokens", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_revoked_tokens_expires_at"), ["expires_at"], unique=False
        )

    op.create_table(
        "asset_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name=op.f("fk_asset_categories_business_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_asset_categories")),
        sa.UniqueConstraint("business_id", "name", name="uq_asset_categories_name"),
    )
    with op.batch_alter_table("asset_categories", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_asset_categories_business_id"), ["business_id"], unique=False
        )

    op.create_table(
        "document_counters",
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("last", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name=op.f("fk_document_counters_business_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("business_id", "kind", name=op.f("pk_document_counters")),
    )
    op.create_table(
        "images",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("content_type", sa.String(length=30), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name=op.f("fk_images_business_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_images")),
    )
    with op.batch_alter_table("images", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_images_business_id"), ["business_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name=op.f("fk_audit_logs_business_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_audit_logs_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    with op.batch_alter_table("audit_logs", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_audit_logs_business_id"), ["business_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_audit_logs_created_at"), ["created_at"], unique=False)
        batch_op.create_index("ix_audit_logs_entity", ["entity_type", "entity_id"], unique=False)

    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("spent_on", sa.Date(), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_expenses_amount_positive")),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name=op.f("fk_expenses_business_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_expenses_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expenses")),
    )
    with op.batch_alter_table("expenses", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_expenses_business_id"), ["business_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_expenses_spent_on"), ["spent_on"], unique=False)

    op.create_table(
        "password_resets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_password_resets_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_resets")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_password_resets_token_hash")),
    )
    with op.batch_alter_table("password_resets", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_password_resets_user_id"), ["user_id"], unique=False)

    op.create_table(
        "asset_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("assigned_by", sa.Integer(), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expected_return", sa.Date(), nullable=True),
        sa.Column("condition_out", sa.String(length=10), nullable=False),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_by", sa.Integer(), nullable=True),
        sa.Column("condition_in", sa.String(length=10), nullable=True),
        sa.Column("return_notes", sa.Text(), nullable=True),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "condition_in IS NULL OR condition_in IN ('new', 'good', 'fair', 'poor', 'damaged')",
            name=op.f("ck_asset_assignments_condition_in_valid"),
        ),
        sa.CheckConstraint(
            "condition_out IN ('new', 'good', 'fair', 'poor', 'damaged')",
            name=op.f("ck_asset_assignments_condition_out_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.id"],
            name=op.f("fk_asset_assignments_asset_id_assets"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by"],
            ["users.id"],
            name=op.f("fk_asset_assignments_assigned_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name=op.f("fk_asset_assignments_business_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["received_by"],
            ["users.id"],
            name=op.f("fk_asset_assignments_received_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_asset_assignments_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_asset_assignments")),
    )
    with op.batch_alter_table("asset_assignments", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_asset_assignments_asset_id"), ["asset_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_asset_assignments_business_id"), ["business_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_asset_assignments_user_id"), ["user_id"], unique=False)
        batch_op.create_index(
            "uq_asset_assignments_open",
            ["asset_id"],
            unique=True,
            postgresql_where=sa.text("returned_at IS NULL"),
        )

    op.create_table(
        "goods_receipts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("purchase_id", sa.Integer(), nullable=False),
        sa.Column("received_by", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name=op.f("fk_goods_receipts_business_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_id"],
            ["purchases.id"],
            name=op.f("fk_goods_receipts_purchase_id_purchases"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["received_by"],
            ["users.id"],
            name=op.f("fk_goods_receipts_received_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_goods_receipts")),
        sa.UniqueConstraint(
            "business_id", "idempotency_key", name="uq_goods_receipts_idempotency_key"
        ),
        sa.UniqueConstraint("business_id", "number", name="uq_goods_receipts_number"),
    )
    with op.batch_alter_table("goods_receipts", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_goods_receipts_business_id"), ["business_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_goods_receipts_purchase_id"), ["purchase_id"], unique=False
        )

    op.create_table(
        "goods_receipt_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("receipt_id", sa.Integer(), nullable=False),
        sa.Column("purchase_item_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_goods_receipt_items_quantity_positive")),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name=op.f("fk_goods_receipt_items_business_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_goods_receipt_items_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_item_id"],
            ["purchase_items.id"],
            name=op.f("fk_goods_receipt_items_purchase_item_id_purchase_items"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["goods_receipts.id"],
            name=op.f("fk_goods_receipt_items_receipt_id_goods_receipts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_goods_receipt_items")),
    )
    with op.batch_alter_table("goods_receipt_items", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_goods_receipt_items_business_id"), ["business_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_goods_receipt_items_receipt_id"), ["receipt_id"], unique=False
        )

    bind = op.get_bind()
    has_data = bind.execute(sa.text("SELECT EXISTS (SELECT 1 FROM users)")).scalar()
    business_id = 0
    if has_data:
        code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))
        business_id = bind.execute(
            sa.text(
                "INSERT INTO businesses (name, join_code) VALUES ('My Business', :code) RETURNING id"
            ),
            {"code": code},
        ).scalar()
    for table in TENANT_TABLES:
        add_business_id(table, business_id)
    for table, kind in NUMBERED.items():
        add_number(table, kind, business_id)

    for table, column in [("categories", "name"), ("products", "sku"), ("assets", "asset_code")]:
        op.drop_constraint(f"uq_{table}_{column}", table, type_="unique")
        op.create_unique_constraint(f"uq_{table}_{column}", table, ["business_id", column])

    op.add_column("users", sa.Column("phone", sa.String(30), nullable=True))
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "users", sa.Column("session_version", sa.Integer(), server_default="0", nullable=False)
    )

    op.add_column(
        "categories",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column("products", sa.Column("image_id", sa.String(36), nullable=True))
    op.add_column(
        "products",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.create_index("ix_products_is_active", "products", ["is_active"])
    op.create_foreign_key(
        "fk_products_image_id_images",
        "products",
        "images",
        ["image_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("suppliers", sa.Column("address", sa.String(300), nullable=True))
    op.add_column(
        "suppliers",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )

    op.add_column("requests", sa.Column("product_id", sa.Integer(), nullable=True))
    op.add_column("requests", sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("requests", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_requests_product_id_products",
        "requests",
        "products",
        ["product_id"],
        ["id"],
        ondelete="SET NULL",
    )
    replace_check(
        "requests",
        "status_valid",
        "status IN ('pending', 'approved', 'rejected', 'fulfilled', 'cancelled')",
    )

    op.alter_column("purchases", "status", type_=sa.String(20), server_default="draft")
    for column in ("ordered_at", "received_at", "cancelled_at"):
        op.add_column("purchases", sa.Column(column, sa.DateTime(timezone=True), nullable=True))
    op.add_column("purchases", sa.Column("request_id", sa.Integer(), nullable=True))
    op.add_column("purchases", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("purchases", sa.Column("cancel_reason", sa.Text(), nullable=True))
    op.create_index("ix_purchases_request_id", "purchases", ["request_id"])
    op.create_foreign_key(
        "fk_purchases_request_id_requests",
        "purchases",
        "requests",
        ["request_id"],
        ["id"],
        ondelete="SET NULL",
    )
    replace_check(
        "purchases",
        "status_valid",
        "status IN ('draft', 'ordered', 'partially_received', 'received', 'cancelled')",
    )
    op.execute("UPDATE purchases SET ordered_at = created_at")
    op.execute("UPDATE purchases SET received_at = updated_at WHERE status = 'received'")
    op.execute("UPDATE purchases SET cancelled_at = updated_at WHERE status = 'cancelled'")
    op.add_column(
        "purchase_items",
        sa.Column("received_quantity", sa.Integer(), server_default="0", nullable=False),
    )
    op.execute(
        """UPDATE purchase_items pi SET received_quantity = pi.quantity
           FROM purchases p WHERE p.id = pi.purchase_id AND p.status = 'received'"""
    )
    op.create_check_constraint(
        op.f("ck_purchase_items_received_in_range"),
        "purchase_items",
        "received_quantity >= 0 AND received_quantity <= quantity",
    )
    op.execute(
        """INSERT INTO goods_receipts (business_id, number, purchase_id, received_by, created_at)
           SELECT business_id,
                  ROW_NUMBER() OVER (PARTITION BY business_id ORDER BY updated_at, id),
                  id, created_by, updated_at
           FROM purchases WHERE status = 'received'"""
    )
    op.execute(
        """INSERT INTO goods_receipt_items
               (business_id, receipt_id, purchase_item_id, product_id, quantity)
           SELECT pi.business_id, g.id, pi.id, pi.product_id, pi.quantity
           FROM purchase_items pi JOIN goods_receipts g ON g.purchase_id = pi.purchase_id"""
    )
    op.execute(
        """INSERT INTO document_counters (business_id, kind, last)
           SELECT business_id, 'grn', MAX(number) FROM goods_receipts GROUP BY business_id"""
    )

    op.add_column("sale_items", sa.Column("unit_cost", sa.Numeric(12, 2), nullable=True))
    op.execute(
        "UPDATE sale_items si SET unit_cost = p.cost_price FROM products p WHERE p.id = si.product_id"
    )
    op.alter_column("sale_items", "unit_cost", nullable=False)
    op.create_check_constraint(
        op.f("ck_sale_items_unit_cost_not_negative"), "sale_items", "unit_cost >= 0"
    )
    op.add_column(
        "sales", sa.Column("vat_rate", sa.Numeric(5, 2), server_default="0", nullable=False)
    )
    op.add_column(
        "sales", sa.Column("vat_amount", sa.Numeric(12, 2), server_default="0", nullable=False)
    )
    op.execute("UPDATE sales SET vat_rate = 16, vat_amount = ROUND(total * 16 / 116, 2)")
    op.add_column(
        "sales",
        sa.Column("status", sa.String(10), server_default="completed", nullable=False),
    )
    op.create_index("ix_sales_status", "sales", ["status"])
    op.create_check_constraint(
        op.f("ck_sales_status_valid"), "sales", "status IN ('completed', 'voided')"
    )
    op.add_column("sales", sa.Column("idempotency_key", sa.String(64), nullable=True))
    op.create_unique_constraint(
        "uq_sales_idempotency_key", "sales", ["business_id", "idempotency_key"]
    )
    op.add_column("sales", sa.Column("voided_by", sa.Integer(), nullable=True))
    op.add_column("sales", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sales", sa.Column("void_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_sales_voided_by_users", "sales", "users", ["voided_by"], ["id"], ondelete="RESTRICT"
    )

    op.add_column("stock_movements", sa.Column("quantity_after", sa.Integer(), nullable=True))
    op.add_column("stock_movements", sa.Column("reference", sa.String(30), nullable=True))
    op.execute(
        """UPDATE stock_movements m SET quantity_after = GREATEST(x.after, 0)
           FROM (SELECT sm.id,
                        p.quantity - COALESCE(SUM(sm.change) OVER (
                            PARTITION BY sm.product_id ORDER BY sm.created_at DESC, sm.id DESC
                            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS after
                 FROM stock_movements sm JOIN products p ON p.id = sm.product_id) x
           WHERE m.id = x.id"""
    )
    op.alter_column("stock_movements", "quantity_after", nullable=False)
    op.execute(
        """UPDATE stock_movements SET reference = SUBSTRING(reason FROM '^(PO-[0-9]+)')
           WHERE type = 'purchase'"""
    )
    op.create_check_constraint(
        op.f("ck_stock_movements_quantity_after_not_negative"),
        "stock_movements",
        "quantity_after >= 0",
    )
    replace_check(
        "stock_movements", "type_valid", "type IN ('purchase', 'sale', 'adjustment', 'sale_void')"
    )
    op.create_index("ix_stock_movements_created_at", "stock_movements", ["created_at"])
    op.create_index("ix_stock_movements_type", "stock_movements", ["type"])

    op.add_column("assets", sa.Column("barcode", sa.String(40), nullable=True))
    op.execute(
        """UPDATE assets SET barcode = 'SP' || LPAD(business_id::text, 4, '0')
                                        || LPAD(number::text, 6, '0')"""
    )
    op.alter_column("assets", "barcode", nullable=False)
    op.create_unique_constraint("uq_assets_barcode", "assets", ["business_id", "barcode"])
    op.add_column("assets", sa.Column("category_id", sa.Integer(), nullable=True))
    op.create_index("ix_assets_category_id", "assets", ["category_id"])
    op.create_foreign_key(
        "fk_assets_category_id_asset_categories",
        "assets",
        "asset_categories",
        ["category_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column("assets", sa.Column("serial_number", sa.String(100), nullable=True))
    op.add_column("assets", sa.Column("purchase_date", sa.Date(), nullable=True))
    op.add_column("assets", sa.Column("purchase_cost", sa.Numeric(12, 2), nullable=True))
    op.add_column(
        "assets", sa.Column("condition", sa.String(10), server_default="good", nullable=False)
    )
    op.add_column("assets", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("assets", sa.Column("image_id", sa.String(36), nullable=True))
    op.create_foreign_key(
        "fk_assets_image_id_images", "assets", "images", ["image_id"], ["id"], ondelete="SET NULL"
    )
    replace_check(
        "assets", "status_valid", "status IN ('available', 'assigned', 'in_repair', 'retired')"
    )
    op.create_check_constraint(
        op.f("ck_assets_condition_valid"),
        "assets",
        "condition IN ('new', 'good', 'fair', 'poor', 'damaged')",
    )
    op.execute(
        """INSERT INTO asset_assignments
               (business_id, asset_id, user_id, assigned_by, assigned_at, condition_out)
           SELECT a.business_id, a.id, a.assigned_to,
                  COALESCE((SELECT MIN(u.id) FROM users u
                            WHERE u.business_id = a.business_id AND u.role = 'admin'),
                           a.assigned_to),
                  a.updated_at, 'good'
           FROM assets a WHERE a.assigned_to IS NOT NULL"""
    )

    op.add_column(
        "repairs", sa.Column("urgency", sa.String(10), server_default="normal", nullable=False)
    )
    op.add_column("repairs", sa.Column("asset_status_before", sa.String(12), nullable=True))
    op.add_column("repairs", sa.Column("resolution", sa.Text(), nullable=True))
    op.add_column("repairs", sa.Column("cost", sa.Numeric(12, 2), nullable=True))
    op.add_column("repairs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("repairs", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("repairs", sa.Column("handled_by", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_repairs_handled_by_users",
        "repairs",
        "users",
        ["handled_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute("UPDATE repairs SET closed_at = updated_at WHERE status = 'done'")
    op.execute(
        """UPDATE repairs SET asset_status_before = CASE WHEN a.assigned_to IS NULL
                                                         THEN 'available' ELSE 'assigned' END
           FROM assets a WHERE a.id = repairs.asset_id AND repairs.status = 'in_progress'"""
    )
    replace_check(
        "repairs", "status_valid", "status IN ('submitted', 'in_progress', 'done', 'rejected')"
    )
    op.create_check_constraint(
        op.f("ck_repairs_urgency_valid"),
        "repairs",
        "urgency IN ('low', 'normal', 'high', 'urgent')",
    )
    op.create_check_constraint(
        op.f("ck_repairs_cost_not_negative"), "repairs", "cost IS NULL OR cost >= 0"
    )

    op.add_column("notifications", sa.Column("link", sa.String(200), nullable=True))


def downgrade():
    raise NotImplementedError(
        "This migration moves data into businesses and cannot be undone automatically. "
        "Restore a database backup taken before upgrading instead."
    )
