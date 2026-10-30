"""Lead WhatsApp chat thread (inbound/outbound after proposal)."""

from alembic import op
import sqlalchemy as sa

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "institute_leads",
        sa.Column("whatsapp_phone", sa.String(length=32), nullable=False, server_default=""),
    )
    op.create_index("ix_institute_leads_whatsapp_phone", "institute_leads", ["whatsapp_phone"])

    op.create_table(
        "institute_lead_chat_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False, server_default="whatsapp"),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("external_id", sa.String(length=190), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["institute_leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id", name="uq_institute_lead_chat_external_id"),
    )
    op.create_index("ix_institute_lead_chat_messages_lead_id", "institute_lead_chat_messages", ["lead_id"])
    op.create_index("ix_institute_lead_chat_messages_created", "institute_lead_chat_messages", ["lead_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_institute_lead_chat_messages_created", table_name="institute_lead_chat_messages")
    op.drop_index("ix_institute_lead_chat_messages_lead_id", table_name="institute_lead_chat_messages")
    op.drop_table("institute_lead_chat_messages")
    op.drop_index("ix_institute_leads_whatsapp_phone", table_name="institute_leads")
    op.drop_column("institute_leads", "whatsapp_phone")
