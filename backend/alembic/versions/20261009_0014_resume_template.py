"""Preferred resume template on user profile."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("preferred_resume_template", sa.String(length=32), nullable=False, server_default="modern"),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "preferred_resume_template")
