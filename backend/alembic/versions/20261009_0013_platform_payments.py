"""Platform Razorpay / payment settings."""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from backend.app.core.platform_defaults import DEFAULT_PAYMENTS

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "platform_settings",
        sa.Column(
            "payments",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
            server_default="{}",
        ),
    )
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE platform_settings SET payments = :payload"),
        {"payload": json.dumps(DEFAULT_PAYMENTS)},
    )


def downgrade() -> None:
    op.drop_column("platform_settings", "payments")
