"""
LinkedIn profile sync engine entry (Master Profile → logged-in member profile).
Launched by the desktop agent with APPLYXAI_RUN_CONFIG pointing at profile sync JSON.
"""

import json
import os
import sys
from pathlib import Path

from modules import run_hooks

RUN_CONFIG_ENV = "APPLYXAI_RUN_CONFIG"


def _load_config() -> dict:
    path = os.environ.get(RUN_CONFIG_ENV, "")
    if not path:
        raise SystemExit(f"{RUN_CONFIG_ENV} is not set")
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    config = _load_config()
    standin = os.environ.get("APPLYXAI_PROFILE_SYNC_STANDIN") == "1"
    driver = None
    if not standin:
        try:
            import modules.open_chrome as open_chrome  # noqa: F401 — creates module-level driver

            driver = open_chrome.driver
            run_hooks.emit({"event": "login_required", "platform": "linkedin"})
        except Exception as exc:
            run_hooks.emit({
                "event": "profile_sync_finished",
                "updated": 0,
                "skipped": 0,
                "failed": 1,
                "stopped": False,
                "error": f"Could not start browser: {exc}",
            })
            return

    from automation.linkedin_profile.sync import run_sync

    try:
        run_sync(config, driver=driver)
    except run_hooks.StopRequested:
        run_hooks.emit({
            "event": "profile_sync_finished",
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "stopped": True,
            "error": "",
        })
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == "__main__":
    main()
