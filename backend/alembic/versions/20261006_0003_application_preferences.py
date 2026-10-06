"""application preferences

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-06 21:04:20.085026+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('application_preferences',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('answers', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_application_preferences_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_application_preferences'))
    )
    with op.batch_alter_table('application_preferences', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_application_preferences_user_id'), ['user_id'], unique=True)



def downgrade() -> None:
    with op.batch_alter_table('application_preferences', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_application_preferences_user_id'))

    op.drop_table('application_preferences')
