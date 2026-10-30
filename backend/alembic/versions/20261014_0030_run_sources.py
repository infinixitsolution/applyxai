"""Job sources and switch count on each automation run.

Revision ID: 0030
Revises: 0029
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column(
        "automation_jobs",
        sa.Column("sources", JSON, nullable=False, server_default=sa.text("'[\"linkedin\"]'")),
    )
    op.add_column("automation_jobs", sa.Column("switch_after", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("automation_jobs", "switch_after")
    op.drop_column("automation_jobs", "sources")
