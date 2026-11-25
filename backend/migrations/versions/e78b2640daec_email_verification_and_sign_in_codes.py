from alembic import op
import sqlalchemy as sa


revision = 'e78b2640daec'
down_revision = '40bb66dad639'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('email_verifications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_email_verifications_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_email_verifications')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_email_verifications_token_hash'))
    )
    with op.batch_alter_table('email_verifications', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_email_verifications_user_id'), ['user_id'], unique=False)

    op.create_table('login_challenges',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('code_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('sends', sa.Integer(), server_default='1', nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_login_challenges_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_login_challenges'))
    )
    with op.batch_alter_table('login_challenges', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_login_challenges_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))

    op.execute("UPDATE users SET email_verified_at = created_at")


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('email_verified_at')

    with op.batch_alter_table('login_challenges', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_login_challenges_user_id'))

    op.drop_table('login_challenges')
    with op.batch_alter_table('email_verifications', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_email_verifications_user_id'))

    op.drop_table('email_verifications')
