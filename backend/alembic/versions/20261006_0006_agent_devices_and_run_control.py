"""agent devices and run control

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-06 22:13:47.447988+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('agent_devices',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('platform', sa.String(length=50), nullable=False),
    sa.Column('agent_version', sa.String(length=32), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=True),
    sa.Column('pairing_code_hash', sa.String(length=64), nullable=True),
    sa.Column('pairing_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('paired_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_agent_devices_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_agent_devices')),
    sa.UniqueConstraint('pairing_code_hash', name=op.f('uq_agent_devices_pairing_code_hash')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_agent_devices_token_hash'))
    )
    with op.batch_alter_table('agent_devices', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_agent_devices_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('automation_jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('device_id', sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column('dry_run', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column('control', sa.String(length=10), server_default='run', nullable=False))
        batch_op.add_column(sa.Column('stop_reason', sa.String(length=32), server_default='', nullable=False))
        batch_op.add_column(sa.Column('event_seq', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('ingest_context', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'),
                                      server_default=sa.text("'{}'"), nullable=False))
        batch_op.add_column(sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_automation_jobs_device_id_agent_devices'), 'agent_devices', ['device_id'], ['id'], ondelete='SET NULL')



def downgrade() -> None:
    with op.batch_alter_table('automation_jobs', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_automation_jobs_device_id_agent_devices'), type_='foreignkey')
        batch_op.drop_column('last_seen_at')
        batch_op.drop_column('ingest_context')
        batch_op.drop_column('event_seq')
        batch_op.drop_column('stop_reason')
        batch_op.drop_column('control')
        batch_op.drop_column('dry_run')
        batch_op.drop_column('device_id')

    with op.batch_alter_table('agent_devices', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_agent_devices_user_id'))

    op.drop_table('agent_devices')
