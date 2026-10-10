"""Mock interview feedback jobs, turn idempotency, TTS cache on messages.

Revision ID: 0026
Revises: 0025
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mock_interview_feedback_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "operation",
            sa.Enum("complete", "regenerate", name="mock_interview_feedback_operation", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("queued", "running", "succeeded", "failed", name="mock_interview_feedback_job_status", native_enum=False),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("presentation_frame_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["mock_interview_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mock_interview_feedback_jobs_session_id", "mock_interview_feedback_jobs", ["session_id"])
    op.create_index("ix_mock_interview_feedback_jobs_user_id", "mock_interview_feedback_jobs", ["user_id"])

    op.add_column("mock_interview_messages", sa.Column("client_turn_id", sa.Uuid(), nullable=True))
    op.create_index(
        "uq_mock_interview_messages_session_client_turn",
        "mock_interview_messages",
        ["session_id", "client_turn_id"],
        unique=True,
        postgresql_where=sa.text("client_turn_id IS NOT NULL"),
        sqlite_where=sa.text("client_turn_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_mock_interview_messages_session_client_turn", table_name="mock_interview_messages")
    op.drop_column("mock_interview_messages", "client_turn_id")
    op.drop_index("ix_mock_interview_feedback_jobs_user_id", table_name="mock_interview_feedback_jobs")
    op.drop_index("ix_mock_interview_feedback_jobs_session_id", table_name="mock_interview_feedback_jobs")
    op.drop_table("mock_interview_feedback_jobs")
