"""Orchestrate LinkedIn profile section sync and emit engine events."""

from __future__ import annotations

import os
import time
from typing import Any

from automation import events as ev
from modules import run_hooks


def _emit(kind: str, **fields: Any) -> None:
    run_hooks.emit({"event": kind, **fields})


def _process_section(section: str, settings: dict, snapshot: dict, driver, *, photo_path: str = "") -> str:
    """Return outcome: updated | skipped | failed."""
    dry_run = bool(settings.get("dry_run"))
    if dry_run:
        return "skipped"
    if driver is None:
        return "updated"
    try:
        from automation.linkedin_profile import browser as browser_sync

        return browser_sync.apply_section(
            driver, section, snapshot, settings, photo_path=photo_path,
        )
    except Exception:
        return "failed"


def run_sync(config: dict, driver=None) -> None:
    profile_sync = config.get("profile_sync") or {}
    settings = config.get("settings") or {}
    snapshot = profile_sync.get("snapshot") or {}
    photo_path = str((config.get("paths") or {}).get("photo_path") or "")
    plan = [p for p in (profile_sync.get("plan") or []) if isinstance(p, dict) and p.get("action") == "fill"]
    sections = [str(p.get("section") or "") for p in plan if p.get("section")]

    _emit(ev.PROFILE_SYNC_STARTED, sections=sections)
    updated = skipped = failed = 0

    if os.environ.get("APPLYXAI_PROFILE_SYNC_STANDIN") == "1":
        driver = None

    for item in plan:
        section = str(item.get("section") or "")
        if not section:
            continue
        _emit(ev.PROFILE_SECTION_STARTED, section=section, action="fill")
        if bool(settings.get("dry_run")):
            _emit(ev.PROFILE_SECTION_SKIPPED, section=section, reason="dry_run")
            skipped += 1
            run_hooks.checkpoint()
            continue
        outcome = _process_section(section, settings, snapshot, driver, photo_path=photo_path)
        if outcome == "updated":
            _emit(ev.PROFILE_SECTION_UPDATED, section=section, field=section, detail="filled from master profile")
            updated += 1
        elif outcome == "skipped":
            _emit(ev.PROFILE_SECTION_SKIPPED, section=section, reason="already_filled")
            skipped += 1
        else:
            _emit(ev.PROFILE_SECTION_SKIPPED, section=section, reason="error")
            failed += 1
        run_hooks.checkpoint()
        time.sleep(0.2)

    _emit(
        ev.PROFILE_MANUAL_REQUIRED,
        item="connections_endorsements",
        hint="Add connections, skill endorsements, and verifications on LinkedIn to raise profile strength.",
    )
    _emit(
        ev.PROFILE_SYNC_FINISHED,
        updated=updated,
        skipped=skipped,
        failed=failed,
        stopped=False,
        error="",
    )
