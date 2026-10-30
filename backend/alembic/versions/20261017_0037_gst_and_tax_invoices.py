"""Platform GST settings JSON and tax_invoices table."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = JSON().with_variant(sa.JSON(), "sqlite")
    op.add_column(
        "platform_settings",
        sa.Column("gst", json_type, nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_table(
        "tax_invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=True),
        sa.Column("invoice_number", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supplier_json", json_type, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("buyer_json", json_type, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("line_items_json", json_type, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("taxable_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cgst_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sgst_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("igst_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="INR"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_number"),
    )
    op.create_index("ix_tax_invoices_user_id", "tax_invoices", ["user_id"])
    op.create_index("ix_tax_invoices_payment_id", "tax_invoices", ["payment_id"])
    op.create_index("ix_tax_invoices_status", "tax_invoices", ["status"])


def downgrade() -> None:
    op.drop_index("ix_tax_invoices_status", table_name="tax_invoices")
    op.drop_index("ix_tax_invoices_payment_id", table_name="tax_invoices")
    op.drop_index("ix_tax_invoices_user_id", table_name="tax_invoices")
    op.drop_table("tax_invoices")
    op.drop_column("platform_settings", "gst")
