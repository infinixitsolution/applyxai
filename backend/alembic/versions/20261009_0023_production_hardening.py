"""Deactivate internal unlimited plan; fix placeholder support email in CMS.

Revision ID: 0023
Revises: 0022
"""

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


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE plans SET is_active = true, price_cents = 199900 "
            "WHERE code = 'unlimited'"
        )
    )
