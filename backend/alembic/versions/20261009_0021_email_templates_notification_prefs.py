"""email templates and user notification email preferences

Revision ID: 0021
Revises: 0020
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from backend.app.core.platform_defaults import DEFAULT_EMAIL_TEMPLATES

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "platform_settings",
        sa.Column(
            "email_templates",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
            server_default="{}",
        ),
    )
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE platform_settings SET email_templates = :payload"),
        {"payload": json.dumps(DEFAULT_EMAIL_TEMPLATES)},
    )

    op.add_column(
        "user_profiles",
        sa.Column(
            "notification_email",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "notification_email")
    op.drop_column("platform_settings", "email_templates")
