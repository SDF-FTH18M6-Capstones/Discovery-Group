"""One receipt can cover several statement rows; add savings

Revision ID: c8b610b54ddf
Revises: 59fe1e85df99
Create Date: 2026-11-27 22:55:28.621862

"""

from alembic import op

revision = "c8b610b54ddf"
down_revision = "59fe1e85df99"
branch_labels = None
depends_on = None

OLD = (
    "'sales', 'loan', 'owner_deposit', 'other_income', 'stock', 'rent', 'utilities', 'wages', "
    "'transport', 'airtime', 'fees', 'loan_repayment', 'withdrawal', 'personal', 'other_expense'"
)
NEW = (
    "'sales', 'loan', 'owner_deposit', 'savings', 'other_income', 'stock', 'rent', 'utilities', "
    "'wages', 'transport', 'airtime', 'fees', 'loan_repayment', 'withdrawal', 'personal', "
    "'other_expense'"
)


def upgrade():
    with op.batch_alter_table("money_transactions") as batch_op:
        batch_op.drop_constraint("uq_money_transactions_receipt", type_="unique")
        batch_op.create_unique_constraint(
            "uq_money_transactions_receipt",
            ["business_id", "receipt", "is_charge", "direction", "amount"],
        )
        batch_op.drop_constraint("category_valid", type_="check")
        batch_op.create_check_constraint("category_valid", f"category IN ({NEW})")


def downgrade():
    op.execute("DELETE FROM money_transactions WHERE category = 'savings'")
    op.execute(
        "DELETE FROM money_transactions a USING money_transactions b "
        "WHERE a.business_id = b.business_id AND a.receipt = b.receipt "
        "AND a.is_charge = b.is_charge AND a.id > b.id"
    )
    with op.batch_alter_table("money_transactions") as batch_op:
        batch_op.drop_constraint("category_valid", type_="check")
        batch_op.create_check_constraint("category_valid", f"category IN ({OLD})")
        batch_op.drop_constraint("uq_money_transactions_receipt", type_="unique")
        batch_op.create_unique_constraint(
            "uq_money_transactions_receipt", ["business_id", "receipt", "is_charge"]
        )
