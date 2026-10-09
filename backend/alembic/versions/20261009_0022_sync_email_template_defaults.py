"""merge new notification and email template defaults into platform_settings

Revision ID: 0022
Revises: 0021
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.app.core.platform_defaults import DEFAULT_EMAIL_TEMPLATES, DEFAULT_NOTIFICATIONS
from backend.app.core.platform_defaults import PLATFORM_SETTINGS_KEY

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        elif value is not None and value != "":
            out[key] = value
    return out


def upgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT notifications, email_templates FROM platform_settings WHERE key = :k"),
        {"k": PLATFORM_SETTINGS_KEY},
    ).mappings().first()
    if row is None:
        return
    stored_notif = row["notifications"] if isinstance(row["notifications"], dict) else json.loads(row["notifications"] or "{}")
    stored_tpl = row["email_templates"] if isinstance(row["email_templates"], dict) else json.loads(row["email_templates"] or "{}")
    merged_notif = _deep_merge(dict(DEFAULT_NOTIFICATIONS), stored_notif)
    ordered_notif = {k: merged_notif[k] for k in DEFAULT_NOTIFICATIONS}
    merged_tpl = _deep_merge(dict(DEFAULT_EMAIL_TEMPLATES), stored_tpl)
    conn.execute(
        sa.text(
            "UPDATE platform_settings SET notifications = :notifications, email_templates = :templates WHERE key = :k"
        ),
        {
            "k": PLATFORM_SETTINGS_KEY,
            "notifications": json.dumps(ordered_notif),
            "templates": json.dumps(merged_tpl),
        },
    )


def downgrade() -> None:
    pass
