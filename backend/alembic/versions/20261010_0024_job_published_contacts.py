"""Store contacts a job posting publishes (name, email, phone).

Revision ID: 0024
Revises: 0023
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()
    if "published_contacts" in {c["name"] for c in sa.inspect(bind).get_columns("jobs")}:
        return
    op.add_column("jobs", sa.Column("published_contacts", JSON, nullable=False, server_default="[]"))


def downgrade() -> None:
    bind = op.get_bind()
    if "published_contacts" not in {c["name"] for c in sa.inspect(bind).get_columns("jobs")}:
        return
    op.drop_column("jobs", "published_contacts")
