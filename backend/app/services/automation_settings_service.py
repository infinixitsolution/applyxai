"""Persist automation run settings separately from screening profile answers."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.services.engine_fields import RUN_SETTINGS_FIELDS, describe, validate_mapping
from backend.app.services.preferences_service import _application_row

_DEFAULTS = {
    "run_in_background": False,
    "pause_before_submit": True,
    "pause_at_failed_question": True,
    "click_gap": 1,
    "close_tabs": False,
    "follow_companies": False,
    "overwrite_previous_answers": False,
    "auto_manage_driver": True,
    "safe_mode": False,
    "keep_screen_awake": True,
    "log_level": "INFO",
    "connect_hr": False,
    "connect_request_message": "",
}


def _current_values(prefs) -> dict:
    answers = dict(prefs.answers or {})
    out = {}
    for key in RUN_SETTINGS_FIELDS:
        if key in answers:
            out[key] = answers[key]
        elif key in _DEFAULTS:
            out[key] = _DEFAULTS[key]
    return out


def get_settings(db: Session, user) -> dict:
    prefs = _application_row(db, user)
    values = _current_values(prefs)
    meta = describe(RUN_SETTINGS_FIELDS)
    warnings = []
    if values.get("run_in_background") and (
        values.get("pause_before_submit") or values.get("pause_at_failed_question")
    ):
        warnings.append(
            "Run in background disables pause-before-submit and pause-on-hard-questions in the browser agent."
        )
    if values.get("connect_hr"):
        warnings.append(
            "LinkedIn Connect to hiring managers is on. LinkedIn limits invites and may restrict the account. Leave this off unless you accept that risk."
        )
    return {
        "values": values,
        "fields": meta,
        "defaults": _DEFAULTS,
        "warnings": warnings,
    }


def update_settings(db: Session, user, changes: dict) -> dict:
    cleaned = validate_mapping(RUN_SETTINGS_FIELDS, changes, allow_null=False)
    prefs = _application_row(db, user)
    answers = dict(prefs.answers or {})
    answers.update(cleaned)
    prefs.answers = answers
    db.commit()
    return get_settings(db, user)


def reset_settings(db: Session, user) -> dict:
    prefs = _application_row(db, user)
    answers = dict(prefs.answers or {})
    for key in RUN_SETTINGS_FIELDS:
        answers.pop(key, None)
    prefs.answers = answers
    db.commit()
    return get_settings(db, user)
