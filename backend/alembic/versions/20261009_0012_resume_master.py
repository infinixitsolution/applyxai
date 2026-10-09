"""Resume master skills and AI metadata."""

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("resumes", sa.Column("master_skills", sa.JSON(), nullable=True))
    op.add_column("resumes", sa.Column("subskills_by_master", sa.JSON(), nullable=True))
    op.add_column("resumes", sa.Column("structured_content", sa.JSON(), nullable=True))
    op.add_column("resumes", sa.Column("ai_metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("resumes", "ai_metadata")
    op.drop_column("resumes", "structured_content")
    op.drop_column("resumes", "subskills_by_master")
    op.drop_column("resumes", "master_skills")
