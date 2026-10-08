"""platform settings

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-09 00:00:00+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from backend.app.core.platform_defaults import DEFAULT_CMS, DEFAULT_NOTIFICATIONS, PLATFORM_SETTINGS_KEY

platform_settings_table = sa.table(
    "platform_settings",
    sa.column("key", sa.String),
    sa.column("cms", sa.JSON),
    sa.column("smtp", sa.JSON),
    sa.column("auth_email", sa.JSON),
    sa.column("notifications", sa.JSON),
)

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_settings",
        sa.Column("key", sa.String(length=32), nullable=False),
        sa.Column("cms", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("smtp", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("auth_email", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("notifications", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_platform_settings")),
    )
    op.bulk_insert(
        platform_settings_table,
        [{
            "key": PLATFORM_SETTINGS_KEY,
            "cms": DEFAULT_CMS,
            "smtp": {},
            "auth_email": {},
            "notifications": DEFAULT_NOTIFICATIONS,
        }],
    )


def downgrade() -> None:
    op.drop_table("platform_settings")
