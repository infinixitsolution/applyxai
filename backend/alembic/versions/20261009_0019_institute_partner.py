"""Institute and partner workspaces, seats, and commissions."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    # Native ADD COLUMN — SQLite batch recreate would DROP plans while subscriptions still
    # reference it, which fails with FOREIGN KEY constraint failed.
    op.add_column(
        "plans",
        sa.Column(
            "kind",
            sa.String(length=32),
            nullable=False,
            server_default="personal",
        ),
    )

    op.create_table(
        "partners",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("organization", sa.String(length=190), nullable=False),
        sa.Column("contact_name", sa.String(length=190), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("referral_code", sa.String(length=16), nullable=False),
        sa.Column("status", sa.Enum("pending", "approved", "active", "suspended", "closed", name="partner_status", native_enum=False, create_constraint=True, length=32), nullable=False),
        sa.Column("kyc_status", sa.Enum("pending", "verified", "rejected", "not_required", name="kyc_status", native_enum=False, create_constraint=True, length=32), nullable=False),
        sa.Column("commission_bps", sa.Integer(), nullable=False),
        sa.Column("gstin", sa.String(length=15), nullable=False),
        sa.Column("pan_number", sa.String(length=10), nullable=False),
        sa.Column("payout_account", sa.String(length=255), nullable=False),
        sa.Column("payout_ifsc", sa.String(length=20), nullable=False),
        sa.Column("kyc_documents", JSON, nullable=False),
        sa.Column("click_count", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partners")),
    )
    op.create_index(op.f("ix_partners_referral_code"), "partners", ["referral_code"], unique=True)
    op.create_index(op.f("ix_partners_status"), "partners", ["status"], unique=False)
    op.create_index(op.f("ix_partners_user_id"), "partners", ["user_id"], unique=True)

    op.create_table(
        "institutes",
        sa.Column("name", sa.String(length=190), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("contact_name", sa.String(length=190), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("institute_type", sa.String(length=32), nullable=False),
        sa.Column("gstin", sa.String(length=15), nullable=False),
        sa.Column("pan_number", sa.String(length=10), nullable=False),
        sa.Column("status", sa.Enum("pending", "active", "suspended", "closed", name="institute_status", native_enum=False, create_constraint=True, length=32), nullable=False),
        sa.Column("partner_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("claimed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("settings", JSON, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["claimed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_institutes")),
    )
    op.create_index(op.f("ix_institutes_email"), "institutes", ["email"], unique=False)
    op.create_index(op.f("ix_institutes_partner_id"), "institutes", ["partner_id"], unique=False)
    op.create_index(op.f("ix_institutes_status"), "institutes", ["status"], unique=False)

    op.add_column("subscriptions", sa.Column("institute_id", sa.Uuid(), nullable=True))
    op.create_index("ix_subscriptions_institute_id", "subscriptions", ["institute_id"])
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_subscriptions_institute_id_institutes",
            "subscriptions",
            "institutes",
            ["institute_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_table(
        "institute_members",
        sa.Column("institute_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Enum("admin", "staff", name="institute_member_role", native_enum=False, create_constraint=True, length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["institute_id"], ["institutes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_institute_members")),
        sa.UniqueConstraint("institute_id", "user_id", name=op.f("uq_institute_members_institute_id_user_id")),
    )
    op.create_index(op.f("ix_institute_members_institute_id"), "institute_members", ["institute_id"], unique=False)
    op.create_index(op.f("ix_institute_members_user_id"), "institute_members", ["user_id"], unique=False)

    op.create_table(
        "institute_seats",
        sa.Column("institute_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Enum("purchased", "assigned", "suspended", "released", "expired", name="seat_status", native_enum=False, create_constraint=True, length=32), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["institute_id"], ["institutes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_institute_seats")),
    )
    op.create_index(op.f("ix_institute_seats_institute_id"), "institute_seats", ["institute_id"], unique=False)
    op.create_index(op.f("ix_institute_seats_status"), "institute_seats", ["status"], unique=False)
    op.create_index(op.f("ix_institute_seats_subscription_id"), "institute_seats", ["subscription_id"], unique=False)

    op.create_table(
        "institute_assignments",
        sa.Column("institute_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_email", sa.String(length=320), nullable=False),
        sa.Column("student_user_id", sa.Uuid(), nullable=True),
        sa.Column("seat_id", sa.Uuid(), nullable=True),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.Enum("invited", "pending_candidate_acceptance", "active", "rejected", "suspended", "released", "expired", "cancelled", name="assignment_status", native_enum=False, create_constraint=True, length=32), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["institute_id"], ["institutes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["seat_id"], ["institute_seats.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["student_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_institute_assignments")),
    )
    op.create_index(op.f("ix_institute_assignments_candidate_email"), "institute_assignments", ["candidate_email"], unique=False)
    op.create_index(op.f("ix_institute_assignments_institute_id"), "institute_assignments", ["institute_id"], unique=False)
    op.create_index(op.f("ix_institute_assignments_seat_id"), "institute_assignments", ["seat_id"], unique=False)
    op.create_index(op.f("ix_institute_assignments_status"), "institute_assignments", ["status"], unique=False)
    op.create_index(op.f("ix_institute_assignments_student_user_id"), "institute_assignments", ["student_user_id"], unique=False)

    op.create_table(
        "institute_invites",
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["institute_assignments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_institute_invites")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_institute_invites_token_hash")),
    )
    op.create_index(op.f("ix_institute_invites_assignment_id"), "institute_invites", ["assignment_id"], unique=False)
    op.create_index(op.f("ix_institute_invites_expires_at"), "institute_invites", ["expires_at"], unique=False)

    op.create_table(
        "partner_attributions",
        sa.Column("partner_id", sa.Uuid(), nullable=False),
        sa.Column("institute_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["institute_id"], ["institutes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partner_attributions")),
        sa.UniqueConstraint("partner_id", "institute_id", name=op.f("uq_partner_attributions_partner_id_institute_id")),
    )
    op.create_index(op.f("ix_partner_attributions_institute_id"), "partner_attributions", ["institute_id"], unique=False)
    op.create_index(op.f("ix_partner_attributions_partner_id"), "partner_attributions", ["partner_id"], unique=False)

    op.create_table(
        "partner_commissions",
        sa.Column("partner_id", sa.Uuid(), nullable=False),
        sa.Column("institute_id", sa.Uuid(), nullable=True),
        sa.Column("subscription_id", sa.Uuid(), nullable=True),
        sa.Column("payment_id", sa.Uuid(), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("rate_bps", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum("accrued", "approved", "void", name="commission_status", native_enum=False, create_constraint=True, length=32), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["institute_id"], ["institutes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partner_commissions")),
        sa.UniqueConstraint("payment_id", name=op.f("uq_partner_commissions_payment_id")),
    )
    op.create_index(op.f("ix_partner_commissions_institute_id"), "partner_commissions", ["institute_id"], unique=False)
    op.create_index(op.f("ix_partner_commissions_partner_id"), "partner_commissions", ["partner_id"], unique=False)
    op.create_index(op.f("ix_partner_commissions_status"), "partner_commissions", ["status"], unique=False)

    op.create_table(
        "partner_payouts",
        sa.Column("partner_id", sa.Uuid(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.Enum("requested", "approved", "paid", "rejected", name="payout_status", native_enum=False, create_constraint=True, length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partner_payouts")),
    )
    op.create_index(op.f("ix_partner_payouts_partner_id"), "partner_payouts", ["partner_id"], unique=False)
    op.create_index(op.f("ix_partner_payouts_status"), "partner_payouts", ["status"], unique=False)

    op.create_table(
        "partner_campaigns",
        sa.Column("partner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("click_count", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partner_campaigns")),
        sa.UniqueConstraint("partner_id", "code", name=op.f("uq_partner_campaigns_partner_id_code")),
    )
    op.create_index(op.f("ix_partner_campaigns_partner_id"), "partner_campaigns", ["partner_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_partner_campaigns_partner_id"), table_name="partner_campaigns")
    op.drop_table("partner_campaigns")
    op.drop_index(op.f("ix_partner_payouts_status"), table_name="partner_payouts")
    op.drop_index(op.f("ix_partner_payouts_partner_id"), table_name="partner_payouts")
    op.drop_table("partner_payouts")
    op.drop_index(op.f("ix_partner_commissions_status"), table_name="partner_commissions")
    op.drop_index(op.f("ix_partner_commissions_partner_id"), table_name="partner_commissions")
    op.drop_index(op.f("ix_partner_commissions_institute_id"), table_name="partner_commissions")
    op.drop_table("partner_commissions")
    op.drop_index(op.f("ix_partner_attributions_partner_id"), table_name="partner_attributions")
    op.drop_index(op.f("ix_partner_attributions_institute_id"), table_name="partner_attributions")
    op.drop_table("partner_attributions")
    op.drop_index(op.f("ix_institute_invites_expires_at"), table_name="institute_invites")
    op.drop_index(op.f("ix_institute_invites_assignment_id"), table_name="institute_invites")
    op.drop_table("institute_invites")
    op.drop_index(op.f("ix_institute_assignments_student_user_id"), table_name="institute_assignments")
    op.drop_index(op.f("ix_institute_assignments_status"), table_name="institute_assignments")
    op.drop_index(op.f("ix_institute_assignments_seat_id"), table_name="institute_assignments")
    op.drop_index(op.f("ix_institute_assignments_institute_id"), table_name="institute_assignments")
    op.drop_index(op.f("ix_institute_assignments_candidate_email"), table_name="institute_assignments")
    op.drop_table("institute_assignments")
    op.drop_index(op.f("ix_institute_seats_subscription_id"), table_name="institute_seats")
    op.drop_index(op.f("ix_institute_seats_status"), table_name="institute_seats")
    op.drop_index(op.f("ix_institute_seats_institute_id"), table_name="institute_seats")
    op.drop_table("institute_seats")
    op.drop_index(op.f("ix_institute_members_user_id"), table_name="institute_members")
    op.drop_index(op.f("ix_institute_members_institute_id"), table_name="institute_members")
    op.drop_table("institute_members")
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_subscriptions_institute_id_institutes", "subscriptions", type_="foreignkey")
    op.drop_index("ix_subscriptions_institute_id", table_name="subscriptions")
    op.drop_column("subscriptions", "institute_id")
    op.drop_index(op.f("ix_institutes_status"), table_name="institutes")
    op.drop_index(op.f("ix_institutes_partner_id"), table_name="institutes")
    op.drop_index(op.f("ix_institutes_email"), table_name="institutes")
    op.drop_table("institutes")
    op.drop_index(op.f("ix_partners_user_id"), table_name="partners")
    op.drop_index(op.f("ix_partners_status"), table_name="partners")
    op.drop_index(op.f("ix_partners_referral_code"), table_name="partners")
    op.drop_table("partners")
    op.drop_column("plans", "kind")
