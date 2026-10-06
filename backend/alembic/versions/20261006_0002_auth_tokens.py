"""auth tokens

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-06 20:55:06.511659+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('auth_tokens',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('purpose', sa.Enum('verify_email', 'reset_password', 'refresh', name='token_purpose', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_auth_tokens_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_auth_tokens')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_auth_tokens_token_hash'))
    )
    with op.batch_alter_table('auth_tokens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_auth_tokens_user_id'), ['user_id'], unique=False)
        batch_op.create_index('ix_auth_tokens_user_purpose', ['user_id', 'purpose'], unique=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('token_version', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('token_version')

    with op.batch_alter_table('auth_tokens', schema=None) as batch_op:
        batch_op.drop_index('ix_auth_tokens_user_purpose')
        batch_op.drop_index(batch_op.f('ix_auth_tokens_user_id'))

    op.drop_table('auth_tokens')
