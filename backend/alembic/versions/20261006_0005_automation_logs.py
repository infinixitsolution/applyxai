"""automation logs

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-06 21:56:50.584360+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('automation_logs',
    sa.Column('automation_job_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('seq', sa.Integer(), nullable=False),
    sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
    sa.Column('level', sa.String(length=10), nullable=False),
    sa.Column('event', sa.String(length=50), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['automation_job_id'], ['automation_jobs.id'], name=op.f('fk_automation_logs_automation_job_id_automation_jobs'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_automation_logs_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_automation_logs'))
    )
    with op.batch_alter_table('automation_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_automation_logs_user_id'), ['user_id'], unique=False)
        batch_op.create_index('uq_automation_logs_run_seq', ['automation_job_id', 'seq'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('automation_logs', schema=None) as batch_op:
        batch_op.drop_index('uq_automation_logs_run_seq')
        batch_op.drop_index(batch_op.f('ix_automation_logs_user_id'))

    op.drop_table('automation_logs')
