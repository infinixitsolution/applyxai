"""Mock interview sessions and messages.

Revision ID: 0025
Revises: 0024
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "mock_interview_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("interview_types", JSON, nullable=False, server_default="[]"),
        sa.Column(
            "status",
            sa.Enum("active", "completed", "abandoned", name="mock_interview_session_status", native_enum=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("feedback", JSON, nullable=True),
        sa.Column("context_snapshot", JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mock_interview_sessions_user_id", "mock_interview_sessions", ["user_id"])
    op.create_index("ix_mock_interview_sessions_application_id", "mock_interview_sessions", ["application_id"])
    op.create_index("ix_mock_interview_sessions_user_created", "mock_interview_sessions", ["user_id", "created_at"])

    op.create_table(
        "mock_interview_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("interviewer", "candidate", name="mock_interview_message_role", native_enum=False),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("meta", JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["mock_interview_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mock_interview_messages_session_id", "mock_interview_messages", ["session_id"])
    op.create_index(
        "ix_mock_interview_messages_session_created", "mock_interview_messages", ["session_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_mock_interview_messages_session_created", table_name="mock_interview_messages")
    op.drop_index("ix_mock_interview_messages_session_id", table_name="mock_interview_messages")
    op.drop_table("mock_interview_messages")
    op.drop_index("ix_mock_interview_sessions_user_created", table_name="mock_interview_sessions")
    op.drop_index("ix_mock_interview_sessions_application_id", table_name="mock_interview_sessions")
    op.drop_index("ix_mock_interview_sessions_user_id", table_name="mock_interview_sessions")
    op.drop_table("mock_interview_sessions")
