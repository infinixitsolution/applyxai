"""Monthly count of resumes created, for the per-plan resume limit.

Revision ID: 0029
Revises: 0028
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("usage_counters", sa.Column("resumes_created", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("usage_counters", "resumes_created")
