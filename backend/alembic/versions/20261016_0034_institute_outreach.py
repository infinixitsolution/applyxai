"""Institute outreach: scrape jobs, leads, proposals, WhatsApp session."""

from alembic import op
import sqlalchemy as sa

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "institute_scrape_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("query", sa.String(length=500), nullable=False),
        sa.Column("location", sa.String(length=190), nullable=False, server_default=""),
        sa.Column("sources", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("max_results", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("leads_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("leads_enriched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_institute_scrape_jobs_created_by_user_id", "institute_scrape_jobs", ["created_by_user_id"])
    op.create_index("ix_institute_scrape_jobs_status", "institute_scrape_jobs", ["status"])

    op.create_table(
        "institute_leads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("source_platform", sa.String(length=32), nullable=False, server_default="google"),
        sa.Column("source_url", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("dedupe_key", sa.String(length=512), nullable=False),
        sa.Column("display_name", sa.String(length=190), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="discovered"),
        sa.Column("institute_id", sa.Uuid(), nullable=True),
        sa.Column("completeness_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["institute_id"], ["institutes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["institute_scrape_jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_institute_leads_dedupe_key"),
    )
    op.create_index("ix_institute_leads_job_id", "institute_leads", ["job_id"])
    op.create_index("ix_institute_leads_source_platform", "institute_leads", ["source_platform"])
    op.create_index("ix_institute_leads_status", "institute_leads", ["status"])
    op.create_index("ix_institute_leads_institute_id", "institute_leads", ["institute_id"])
    op.create_index("ix_institute_leads_dedupe_key", "institute_leads", ["dedupe_key"])

    op.create_table(
        "institute_lead_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("raw_snippets", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["institute_leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lead_id"),
    )
    op.create_index("ix_institute_lead_profiles_lead_id", "institute_lead_profiles", ["lead_id"], unique=True)

    op.create_table(
        "institute_outreach_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("html", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("provider_response", sa.Text(), nullable=False, server_default=""),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["institute_leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_institute_outreach_messages_lead_id", "institute_outreach_messages", ["lead_id"])
    op.create_index("ix_institute_outreach_messages_channel", "institute_outreach_messages", ["channel"])
    op.create_index("ix_institute_outreach_messages_status", "institute_outreach_messages", ["status"])

    op.create_table(
        "whatsapp_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_key", sa.String(length=32), nullable=False, server_default="default"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="disconnected"),
        sa.Column("session_path", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_key"),
    )


def downgrade() -> None:
    op.drop_table("whatsapp_sessions")
    op.drop_table("institute_outreach_messages")
    op.drop_table("institute_lead_profiles")
    op.drop_table("institute_leads")
    op.drop_table("institute_scrape_jobs")
