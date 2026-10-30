"""Candidate referrals, payout transfer ids, institute-owned outreach, Naukri default on.

Revision ID: 0040
Revises: 0039
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0040"
down_revision: Union[str, None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column("users", sa.Column("referral_code", sa.String(length=16), nullable=True))
    op.create_index("ix_users_referral_code", "users", ["referral_code"], unique=True)

    op.create_table(
        "candidate_referrals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("referrer_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("referred_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="attributed"),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("referred_user_id", name="uq_candidate_referrals_referred_user_id"),
    )
    op.create_index("ix_candidate_referrals_referrer_user_id", "candidate_referrals", ["referrer_user_id"])
    op.create_index("ix_candidate_referrals_code", "candidate_referrals", ["code"])

    op.add_column("partner_payouts", sa.Column("provider_transfer_id", sa.String(length=255), nullable=False, server_default=""))

    op.add_column(
        "institute_scrape_jobs",
        sa.Column("owner_institute_id", sa.Uuid(), sa.ForeignKey("institutes.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_institute_scrape_jobs_owner_institute_id", "institute_scrape_jobs", ["owner_institute_id"])
    op.add_column(
        "institute_leads",
        sa.Column("owner_institute_id", sa.Uuid(), sa.ForeignKey("institutes.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_institute_leads_owner_institute_id", "institute_leads", ["owner_institute_id"])

    # Existing DBs stored naukri=false at 0031; flip the default on for this leftovers close-out.
    import json

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT key, job_sources FROM platform_settings")).mappings().all()
    for row in rows:
        sources = row["job_sources"]
        if isinstance(sources, str):
            try:
                sources = json.loads(sources)
            except ValueError:
                sources = {}
        if not isinstance(sources, dict):
            sources = {}
        merged = dict(sources)
        merged["linkedin"] = bool(merged.get("linkedin", True))
        merged["naukri"] = True
        bind.execute(
            sa.text("UPDATE platform_settings SET job_sources = :js WHERE key = :key").bindparams(
                sa.bindparam("js", type_=JSON)
            ),
            {"js": merged, "key": row["key"]},
        )


def downgrade() -> None:
    op.drop_index("ix_institute_leads_owner_institute_id", table_name="institute_leads")
    op.drop_column("institute_leads", "owner_institute_id")
    op.drop_index("ix_institute_scrape_jobs_owner_institute_id", table_name="institute_scrape_jobs")
    op.drop_column("institute_scrape_jobs", "owner_institute_id")
    op.drop_column("partner_payouts", "provider_transfer_id")
    op.drop_index("ix_candidate_referrals_code", table_name="candidate_referrals")
    op.drop_index("ix_candidate_referrals_referrer_user_id", table_name="candidate_referrals")
    op.drop_table("candidate_referrals")
    op.drop_index("ix_users_referral_code", table_name="users")
    op.drop_column("users", "referral_code")
