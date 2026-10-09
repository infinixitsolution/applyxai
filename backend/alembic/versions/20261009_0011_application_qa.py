"""application qa columns

Revision ID: 0011
Revises: 0010
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column("application_preferences", sa.Column("human_questions", JSON, nullable=False, server_default="[]"))
    op.add_column("application_preferences", sa.Column("ai_applications_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("application_preferences", sa.Column("user_information_all", sa.Text(), nullable=False, server_default=""))
    op.add_column("application_preferences", sa.Column("ai_policy", JSON, nullable=False, server_default='{"deny_label_contains": ["gender", "race", "ethnicity", "disability", "veteran", "sexual"]}'))


def downgrade() -> None:
    op.drop_column("application_preferences", "ai_policy")
    op.drop_column("application_preferences", "user_information_all")
    op.drop_column("application_preferences", "ai_applications_enabled")
    op.drop_column("application_preferences", "human_questions")
