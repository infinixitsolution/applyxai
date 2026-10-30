"""Master profile extended data and photo storage key."""

from alembic import op
import sqlalchemy as sa

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("photo_storage_key", sa.String(length=512), nullable=True))
    op.add_column("user_profiles", sa.Column("master_data", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("user_profiles", sa.Column("master_migrated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("user_profiles", "master_migrated_at")
    op.drop_column("user_profiles", "master_data")
    op.drop_column("user_profiles", "photo_storage_key")
