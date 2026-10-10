"""Deactivate internal unlimited plan; fix placeholder support email in CMS.

Revision ID: 0023
Revises: 0022
"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.app.core.platform_defaults import PLATFORM_SETTINGS_KEY

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE plans SET is_active = false, price_cents = 0 WHERE code = 'unlimited'")
    )
    if conn.dialect.name == "postgresql":
        conn.execute(
            sa.text(
                """
                UPDATE platform_settings
                SET cms = jsonb_set(
                    cms,
                    '{branding,contact_email}',
                    '"support@applyxai.com"'::jsonb,
                    true
                )
                WHERE key = :key
                  AND (cms->'branding'->>'contact_email') IN ('support@applyxai.example', '')
                """
            ),
            {"key": PLATFORM_SETTINGS_KEY},
        )
        return
    row = conn.execute(
        sa.text("SELECT cms FROM platform_settings WHERE key = :key"),
        {"key": PLATFORM_SETTINGS_KEY},
    ).fetchone()
    if not row or not row[0]:
        return
    cms = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    branding = cms.get("branding") if isinstance(cms.get("branding"), dict) else {}
    email = str(branding.get("contact_email") or "")
    if email not in ("support@applyxai.example", ""):
        return
    cms = dict(cms)
    cms["branding"] = {**branding, "contact_email": "support@applyxai.com"}
    conn.execute(
        sa.text("UPDATE platform_settings SET cms = :cms WHERE key = :key"),
        {"cms": json.dumps(cms), "key": PLATFORM_SETTINGS_KEY},
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE plans SET is_active = true, price_cents = 199900 "
            "WHERE code = 'unlimited'"
        )
    )
