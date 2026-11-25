from alembic import op
import sqlalchemy as sa


revision = '497d77943dc1'
down_revision = 'fc5258fdfa87'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('otp_attempts', sa.Integer(), server_default='0', nullable=False))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('otp_attempts')

