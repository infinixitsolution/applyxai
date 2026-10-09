"""Partner commission mode: percent, flat payment, flat seat, flat candidate."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "partners",
        sa.Column("commission_mode", sa.String(length=32), nullable=False, server_default="percent_payment"),
    )
    op.add_column(
        "partners",
        sa.Column("commission_flat_cents", sa.Integer(), nullable=False, server_default="0"),
    )

    op.add_column(
        "partner_commissions",
        sa.Column("commission_mode", sa.String(length=32), nullable=False, server_default="percent_payment"),
    )
    op.add_column(
        "partner_commissions",
        sa.Column("rate_flat_cents", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("partner_commissions", sa.Column("assignment_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_partner_commissions_assignment_id"),
        "partner_commissions",
        ["assignment_id"],
        unique=False,
    )
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_partner_commissions_assignment_id_institute_assignments",
            "partner_commissions",
            "institute_assignments",
            ["assignment_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_unique_constraint(
            "uq_partner_commissions_assignment_id",
            "partner_commissions",
            ["assignment_id"],
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("uq_partner_commissions_assignment_id", "partner_commissions", type_="unique")
        op.drop_constraint(
            "fk_partner_commissions_assignment_id_institute_assignments",
            "partner_commissions",
            type_="foreignkey",
        )
    op.drop_index(op.f("ix_partner_commissions_assignment_id"), table_name="partner_commissions")
    op.drop_column("partner_commissions", "assignment_id")
    op.drop_column("partner_commissions", "rate_flat_cents")
    op.drop_column("partner_commissions", "commission_mode")
    op.drop_column("partners", "commission_flat_cents")
    op.drop_column("partners", "commission_mode")
