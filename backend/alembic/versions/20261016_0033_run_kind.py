"""Automation run kind (job apply vs LinkedIn profile sync)."""

from alembic import op
import sqlalchemy as sa

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "automation_jobs",
        sa.Column("run_kind", sa.String(length=32), nullable=False, server_default="job_apply"),
    )
    op.add_column(
        "automation_jobs",
        sa.Column("run_options", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("automation_jobs", "run_options")
    op.drop_column("automation_jobs", "run_kind")
