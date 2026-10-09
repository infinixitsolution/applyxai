"""platform ai settings

Revision ID: 0010
Revises: 0009
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from backend.app.core.platform_defaults import DEFAULT_AI

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "platform_settings",
        sa.Column(
            "ai",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
            server_default="{}",
        ),
    )
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE platform_settings SET ai = :payload"),
        {"payload": json.dumps(DEFAULT_AI)},
    )


def downgrade() -> None:
    op.drop_column("platform_settings", "ai")
