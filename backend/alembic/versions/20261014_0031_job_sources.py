"""Admin activation flags for LinkedIn and Naukri.

Revision ID: 0031
Revises: 0030
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column(
        "platform_settings",
        sa.Column("job_sources", JSON, nullable=False, server_default=sa.text("'{\"linkedin\": true, \"naukri\": false}'")),
    )


def downgrade() -> None:
    op.drop_column("platform_settings", "job_sources")
