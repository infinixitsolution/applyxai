"""Render admin-editable email and notification copy from platform settings."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.platform_defaults import DEFAULT_EMAIL_TEMPLATES, DEFAULT_NOTIFICATIONS
from backend.app.services import platform_settings_service as ps
from backend.app.services.email_service import Email

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        elif value is not None:
            out[key] = value
    return out


def get_templates(db: Session) -> dict:
    from backend.app.models import PlatformSettings
    from backend.app.core.platform_defaults import PLATFORM_SETTINGS_KEY

    from backend.app.services import platform_settings_service as ps

    row = db.get(PlatformSettings, PLATFORM_SETTINGS_KEY)
    stored = ps._stored_email_templates(db, row) if row is not None else {}
    return _deep_merge(dict(DEFAULT_EMAIL_TEMPLATES), stored)


def render(template: str, variables: dict[str, str]) -> str:
    if not template:
        return ""

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return variables.get(key, "")

    return _PLACEHOLDER.sub(repl, template)


def _base_vars(db: Session) -> dict[str, str]:
    auth = ps.get_effective_auth(db)
    cms = ps.get_effective_cms(db)
    app_name = str(cms.get("branding", {}).get("app_name") or auth.app_name)
    return {
        "app_name": app_name,
        "frontend_url": auth.frontend_url,
        "verification_hours": str(auth.verification_hours),
        "password_reset_minutes": str(auth.password_reset_minutes),
    }


def auth_email(db: Session, kind: str, to: str, **variables: str) -> Email:
    templates = get_templates(db)
    block = (templates.get("auth") or {}).get(kind) or {}
    defaults = (DEFAULT_EMAIL_TEMPLATES.get("auth") or {}).get(kind) or {}
    subject_tpl = block.get("subject") or defaults.get("subject") or ""
    body_tpl = block.get("body") or defaults.get("body") or ""
    html_tpl = block.get("html") or defaults.get("html") or ""
    vars_merged = {**_base_vars(db), **{k: str(v) for k, v in variables.items() if k != "to"}}
    subject = render(subject_tpl, vars_merged)
    body = render(body_tpl, vars_merged)
    html = render(html_tpl, vars_merged) if html_tpl else ""
    return Email(to=to, subject=subject, body=body, html=html)


def event_template_block(db: Session, event_type: str) -> dict[str, Any]:
    templates = get_templates(db)
    block = (templates.get("events") or {}).get(event_type) or {}
    defaults = (DEFAULT_EMAIL_TEMPLATES.get("events") or {}).get(event_type) or {}
    return _deep_merge(defaults, block)


def event_copy(db: Session, event_type: str, channel: str, **variables: str) -> str:
    block = event_template_block(db, event_type)
    tpl = block.get(channel) or ""
    vars_merged = {**_base_vars(db), **{k: str(v) for k, v in variables.items()}}
    return render(tpl, vars_merged)


def notification_types() -> list[str]:
    return list(DEFAULT_NOTIFICATIONS.keys())
