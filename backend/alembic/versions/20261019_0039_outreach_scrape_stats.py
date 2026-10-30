"""Outreach scrape job metrics (stats JSON, leads_updated)."""

from alembic import op
import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "institute_scrape_jobs",
        sa.Column("leads_updated", sa.Integer(), server_default="0", nullable=False),
    )
    json_type = sa.JSON().with_variant(JSONB(astext_type=sa.Text()), "postgresql")
    op.add_column(
        "institute_scrape_jobs",
        sa.Column("stats", json_type, server_default="{}", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("institute_scrape_jobs", "stats")
    op.drop_column("institute_scrape_jobs", "leads_updated")
