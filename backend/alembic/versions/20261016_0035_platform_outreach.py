"""Platform settings: outreach (Firecrawl API key)."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = JSON().with_variant(sa.JSON(), "sqlite")
    op.add_column(
        "platform_settings",
        sa.Column("outreach", json_type, nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("platform_settings", "outreach")
