"""payments and billing events

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-06 23:17:18.638433+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('billing_events',
    sa.Column('provider', sa.String(length=32), nullable=False),
    sa.Column('event_id', sa.String(length=255), nullable=False),
    sa.Column('event_type', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('subscription_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], name=op.f('fk_billing_events_subscription_id_subscriptions'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_billing_events_user_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_billing_events')),
    sa.UniqueConstraint('provider', 'event_id', name=op.f('uq_billing_events_provider_event_id'))
    )
    with op.batch_alter_table('billing_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_billing_events_user_id'), ['user_id'], unique=False)

    op.create_table('payments',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('subscription_id', sa.Uuid(), nullable=True),
    sa.Column('provider', sa.String(length=32), nullable=False),
    sa.Column('provider_payment_id', sa.String(length=255), nullable=False),
    sa.Column('amount_cents', sa.Integer(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('method', sa.String(length=32), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=False),
    sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], name=op.f('fk_payments_subscription_id_subscriptions'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_payments_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_payments')),
    sa.UniqueConstraint('provider_payment_id', name=op.f('uq_payments_provider_payment_id'))
    )
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_payments_subscription_id'), ['subscription_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_payments_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_payments_user_id'))
        batch_op.drop_index(batch_op.f('ix_payments_subscription_id'))

    op.drop_table('payments')
    with op.batch_alter_table('billing_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_billing_events_user_id'))

    op.drop_table('billing_events')
