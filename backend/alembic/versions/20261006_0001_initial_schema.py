"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-10-06 20:44:55.616903+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('jobs',
    sa.Column('external_id', sa.String(length=64), nullable=False),
    sa.Column('platform', sa.String(length=32), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('company', sa.String(length=255), nullable=False),
    sa.Column('location', sa.String(length=255), nullable=False),
    sa.Column('job_url', sa.String(length=1024), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('salary_min', sa.Integer(), nullable=True),
    sa.Column('salary_max', sa.Integer(), nullable=True),
    sa.Column('employment_type', sa.String(length=32), nullable=False),
    sa.Column('work_setting', sa.String(length=32), nullable=False),
    sa.Column('experience_level', sa.String(length=32), nullable=False),
    sa.Column('discovered_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_jobs')),
    sa.UniqueConstraint('platform', 'external_id', name=op.f('uq_jobs_platform_external_id'))
    )
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_jobs_company'), ['company'], unique=False)
        batch_op.create_index(batch_op.f('ix_jobs_discovered_at'), ['discovered_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_jobs_external_id'), ['external_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_jobs_platform'), ['platform'], unique=False)
        batch_op.create_index(batch_op.f('ix_jobs_title'), ['title'], unique=False)

    op.create_table('plans',
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('limits', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('price_cents', sa.Integer(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('interval', sa.String(length=16), nullable=False),
    sa.Column('provider_plan_id', sa.String(length=255), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_plans')),
    sa.UniqueConstraint('code', name=op.f('uq_plans_code'))
    )
    op.create_table('users',
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('first_name', sa.String(length=100), nullable=False),
    sa.Column('last_name', sa.String(length=100), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_verified', sa.Boolean(), nullable=False),
    sa.Column('is_admin', sa.Boolean(), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users'))
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)

    op.create_table('automation_jobs',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.Enum('queued', 'running', 'paused', 'completed', 'failed', 'cancelled', name='automation_status', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('current_job', sa.String(length=500), nullable=False),
    sa.Column('total_jobs', sa.Integer(), nullable=False),
    sa.Column('successful_count', sa.Integer(), nullable=False),
    sa.Column('failed_count', sa.Integer(), nullable=False),
    sa.Column('skipped_count', sa.Integer(), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=False),
    sa.Column('task_id', sa.String(length=255), nullable=False),
    sa.Column('worker_id', sa.String(length=255), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_automation_jobs_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_automation_jobs'))
    )
    with op.batch_alter_table('automation_jobs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_automation_jobs_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_automation_jobs_user_id'), ['user_id'], unique=False)
        batch_op.create_index('uq_automation_jobs_one_active_per_user', ['user_id'], unique=True, postgresql_where=sa.text("status IN ('queued', 'running', 'paused')"), sqlite_where=sa.text("status IN ('queued', 'running', 'paused')"))

    op.create_table('resumes',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('storage_path', sa.String(length=512), nullable=False),
    sa.Column('file_type', sa.String(length=16), nullable=False),
    sa.Column('file_size', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_resumes_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_resumes')),
    sa.UniqueConstraint('storage_path', name=op.f('uq_resumes_storage_path'))
    )
    with op.batch_alter_table('resumes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_resumes_user_id'), ['user_id'], unique=False)
        batch_op.create_index('uq_resumes_one_default_per_user', ['user_id'], unique=True, postgresql_where=sa.text('is_default'), sqlite_where=sa.text('is_default'))

    op.create_table('search_configs',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('keywords', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('location', sa.String(length=255), nullable=False),
    sa.Column('easy_apply_only', sa.Boolean(), nullable=False),
    sa.Column('experience_level', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('job_type', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('on_site', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('companies', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('date_posted', sa.String(length=32), nullable=False),
    sa.Column('sort_by', sa.String(length=32), nullable=False),
    sa.Column('salary_min', sa.Integer(), nullable=True),
    sa.Column('salary_max', sa.Integer(), nullable=True),
    sa.Column('extra', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_search_configs_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_search_configs'))
    )
    with op.batch_alter_table('search_configs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_search_configs_user_id'), ['user_id'], unique=True)

    op.create_table('subscriptions',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('plan_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.Enum('pending', 'trialing', 'active', 'past_due', 'cancelled', 'expired', name='subscription_status', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('provider', sa.String(length=32), nullable=False),
    sa.Column('provider_customer_id', sa.String(length=255), nullable=False),
    sa.Column('provider_subscription_id', sa.String(length=255), nullable=True),
    sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=True),
    sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], name=op.f('fk_subscriptions_plan_id_plans'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_subscriptions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_subscriptions')),
    sa.UniqueConstraint('provider_subscription_id', name=op.f('uq_subscriptions_provider_subscription_id'))
    )
    with op.batch_alter_table('subscriptions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_subscriptions_plan_id'), ['plan_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_subscriptions_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_subscriptions_user_id'), ['user_id'], unique=False)

    op.create_table('usage_counters',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('period', sa.String(length=7), nullable=False),
    sa.Column('applications', sa.Integer(), nullable=False),
    sa.Column('jobs_discovered', sa.Integer(), nullable=False),
    sa.Column('runtime_seconds', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_usage_counters_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_usage_counters')),
    sa.UniqueConstraint('user_id', 'period', name=op.f('uq_usage_counters_user_id_period'))
    )
    with op.batch_alter_table('usage_counters', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_usage_counters_user_id'), ['user_id'], unique=False)

    op.create_table('user_profiles',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('phone', sa.String(length=32), nullable=False),
    sa.Column('headline', sa.String(length=255), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('skills', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('preferred_locations', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('preferred_roles', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('experience_years', sa.Integer(), nullable=True),
    sa.Column('current_title', sa.String(length=255), nullable=False),
    sa.Column('current_company', sa.String(length=255), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_profiles_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_profiles'))
    )
    with op.batch_alter_table('user_profiles', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_profiles_user_id'), ['user_id'], unique=True)

    op.create_table('applications',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('job_id', sa.Uuid(), nullable=False),
    sa.Column('resume_id', sa.Uuid(), nullable=True),
    sa.Column('automation_job_id', sa.Uuid(), nullable=True),
    sa.Column('status', sa.Enum('discovered', 'queued', 'running', 'applied', 'failed', 'skipped', 'external', 'cancelled', name='application_status', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('failure_reason', sa.Text(), nullable=False),
    sa.Column('external_application_id', sa.String(length=255), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['automation_job_id'], ['automation_jobs.id'], name=op.f('fk_applications_automation_job_id_automation_jobs'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], name=op.f('fk_applications_job_id_jobs'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], name=op.f('fk_applications_resume_id_resumes'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_applications_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_applications')),
    sa.UniqueConstraint('user_id', 'job_id', name=op.f('uq_applications_user_id_job_id'))
    )
    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_applications_automation_job_id'), ['automation_job_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_applications_job_id'), ['job_id'], unique=False)
        batch_op.create_index('ix_applications_user_applied_at', ['user_id', 'applied_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_applications_user_id'), ['user_id'], unique=False)
        batch_op.create_index('ix_applications_user_status', ['user_id', 'status'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.drop_index('ix_applications_user_status')
        batch_op.drop_index(batch_op.f('ix_applications_user_id'))
        batch_op.drop_index('ix_applications_user_applied_at')
        batch_op.drop_index(batch_op.f('ix_applications_job_id'))
        batch_op.drop_index(batch_op.f('ix_applications_automation_job_id'))

    op.drop_table('applications')
    with op.batch_alter_table('user_profiles', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_profiles_user_id'))

    op.drop_table('user_profiles')
    with op.batch_alter_table('usage_counters', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_usage_counters_user_id'))

    op.drop_table('usage_counters')
    with op.batch_alter_table('subscriptions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_subscriptions_user_id'))
        batch_op.drop_index(batch_op.f('ix_subscriptions_status'))
        batch_op.drop_index(batch_op.f('ix_subscriptions_plan_id'))

    op.drop_table('subscriptions')
    with op.batch_alter_table('search_configs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_search_configs_user_id'))

    op.drop_table('search_configs')
    with op.batch_alter_table('resumes', schema=None) as batch_op:
        batch_op.drop_index('uq_resumes_one_default_per_user', postgresql_where=sa.text('is_default'), sqlite_where=sa.text('is_default'))
        batch_op.drop_index(batch_op.f('ix_resumes_user_id'))

    op.drop_table('resumes')
    with op.batch_alter_table('automation_jobs', schema=None) as batch_op:
        batch_op.drop_index('uq_automation_jobs_one_active_per_user', postgresql_where=sa.text("status IN ('queued', 'running', 'paused')"), sqlite_where=sa.text("status IN ('queued', 'running', 'paused')"))
        batch_op.drop_index(batch_op.f('ix_automation_jobs_user_id'))
        batch_op.drop_index(batch_op.f('ix_automation_jobs_status'))

    op.drop_table('automation_jobs')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_email'))

    op.drop_table('users')
    op.drop_table('plans')
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_jobs_title'))
        batch_op.drop_index(batch_op.f('ix_jobs_platform'))
        batch_op.drop_index(batch_op.f('ix_jobs_external_id'))
        batch_op.drop_index(batch_op.f('ix_jobs_discovered_at'))
        batch_op.drop_index(batch_op.f('ix_jobs_company'))

    op.drop_table('jobs')
