"""Link generated resumes to applications."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "application_id" in {c["name"] for c in insp.get_columns("resumes")}:
        return
    with op.batch_alter_table("resumes") as batch_op:
        batch_op.add_column(sa.Column("application_id", sa.Uuid(), nullable=True))
        batch_op.create_index("ix_resumes_application_id", ["application_id"])
        batch_op.create_foreign_key(
            "fk_resumes_application_id_applications",
            "applications",
            ["application_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "application_id" not in {c["name"] for c in insp.get_columns("resumes")}:
        return
    with op.batch_alter_table("resumes") as batch_op:
        batch_op.drop_constraint("fk_resumes_application_id_applications", type_="foreignkey")
        batch_op.drop_index("ix_resumes_application_id")
        batch_op.drop_column("application_id")
