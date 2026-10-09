"""Browser-assisted one-click agent connect sessions."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_connect_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_name", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("platform", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("agent_version", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column("deliver_token", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["agent_devices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_connect_sessions_expires", "agent_connect_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_connect_sessions_expires", table_name="agent_connect_sessions")
    op.drop_table("agent_connect_sessions")
