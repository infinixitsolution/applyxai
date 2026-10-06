"""admin audit log

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-06 23:38:23.593128+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('admin_actions',
    sa.Column('admin_id', sa.Uuid(), nullable=True),
    sa.Column('admin_email', sa.String(length=320), nullable=False),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('target_user_id', sa.Uuid(), nullable=True),
    sa.Column('target', sa.String(length=320), nullable=False),
    sa.Column('details', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['admin_id'], ['users.id'], name=op.f('fk_admin_actions_admin_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['target_user_id'], ['users.id'], name=op.f('fk_admin_actions_target_user_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_admin_actions'))
    )
    with op.batch_alter_table('admin_actions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_admin_actions_admin_id'), ['admin_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_admin_actions_target_user_id'), ['target_user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('admin_actions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_admin_actions_target_user_id'))
        batch_op.drop_index(batch_op.f('ix_admin_actions_admin_id'))

    op.drop_table('admin_actions')
