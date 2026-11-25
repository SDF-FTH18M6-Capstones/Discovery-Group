from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '9752b64b2612'
down_revision = '497d77943dc1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('is_verified')
        batch_op.drop_column('otp_hash')
        batch_op.drop_column('otp_expires_at')
        batch_op.drop_column('otp_attempts')


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('otp_attempts', sa.INTEGER(), server_default=sa.text('0'), autoincrement=False, nullable=False))
        batch_op.add_column(sa.Column('otp_expires_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('otp_hash', sa.VARCHAR(length=255), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('is_verified', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False))

