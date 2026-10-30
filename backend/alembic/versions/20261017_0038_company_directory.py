"""Company directory profiles for admin HR contact enrichment."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "company_directory_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_key", sa.String(length=255), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="idle"),
        sa.Column("contacts", JSON, nullable=False, server_default="[]"),
        sa.Column("job_links", JSON, nullable=False, server_default="[]"),
        sa.Column("source_pages", JSON, nullable=False, server_default="[]"),
        sa.Column("last_enriched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_key"),
    )
    op.create_index("ix_company_directory_profiles_company_key", "company_directory_profiles", ["company_key"])
    op.create_index("ix_company_directory_profiles_status", "company_directory_profiles", ["status"])


def downgrade() -> None:
    op.drop_index("ix_company_directory_profiles_status", table_name="company_directory_profiles")
    op.drop_index("ix_company_directory_profiles_company_key", table_name="company_directory_profiles")
    op.drop_table("company_directory_profiles")
