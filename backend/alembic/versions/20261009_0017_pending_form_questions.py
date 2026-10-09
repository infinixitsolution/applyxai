"""Questions seen during LinkedIn Easy Apply, pending user answers."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column(
        "application_preferences",
        sa.Column("pending_form_questions", JSON, nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("application_preferences", "pending_form_questions")
