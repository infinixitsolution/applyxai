"""Education and work history on user profile."""

from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("education", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("user_profiles", sa.Column("work_history", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("user_profiles", "work_history")
    op.drop_column("user_profiles", "education")
