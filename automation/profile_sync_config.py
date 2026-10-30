"""Build JSON config for runLinkedInProfileSync.py."""

from __future__ import annotations

from pathlib import Path


def build_profile_sync_config(
    profile_sync: dict,
    *,
    run_dir: str | Path,
    photo_path: str | Path | None = None,
) -> dict:
    run = Path(run_dir).resolve()
    settings = dict(profile_sync.get("settings") or {})
    settings.setdefault("fill_empty_only", True)
    settings.setdefault("dry_run", False)
    return {
        "profile_sync": {
            "snapshot": profile_sync.get("snapshot") or {},
            "plan": profile_sync.get("plan") or [],
        },
        "settings": settings,
        "paths": {
            "run_dir": run.as_posix(),
            "photo_path": Path(photo_path).resolve().as_posix() if photo_path else "",
            "logs_folder_path": (run / "logs").as_posix() + "/",
        },
    }
