"""Run runAiBot.py when frozen PyInstaller builds cannot execute a .py script path."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

ENGINE_FLAG = "--applyxai-engine"
PROFILE_SYNC_FLAG = "--applyxai-profile-sync"


def engine_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def engine_script() -> Path:
    return engine_root() / "runAiBot.py"


def profile_sync_script() -> Path:
    return engine_root() / "runLinkedInProfileSync.py"


def frozen_engine_executable() -> str:
    """Prefer the CLI exe when the GUI exe would otherwise spawn itself."""
    exe = Path(sys.executable)
    if getattr(sys, "frozen", False) and "GUI" in exe.stem.upper():
        cli = exe.with_name("ApplyXAI-Agent.exe")
        if cli.is_file():
            return str(cli)
    return sys.executable


def engine_argv(*, profile_sync: bool = False) -> list[str]:
    if getattr(sys, "frozen", False):
        flag = PROFILE_SYNC_FLAG if profile_sync else ENGINE_FLAG
        return [frozen_engine_executable(), flag]
    script = profile_sync_script() if profile_sync else engine_script()
    return [sys.executable, str(script)]


def run_engine_child_if_requested() -> bool:
    """If argv contains an engine flag, run the matching script and return True."""
    profile = PROFILE_SYNC_FLAG in sys.argv
    job = ENGINE_FLAG in sys.argv
    if not profile and not job:
        return False
    sys.argv = [a for a in sys.argv if a not in (ENGINE_FLAG, PROFILE_SYNC_FLAG)]
    script = profile_sync_script() if profile else engine_script()
    if not script.is_file():
        print(f"Automation engine missing from bundle: {script}", file=sys.stderr)
        raise SystemExit(1)
    runpy.run_path(str(script), run_name="__main__")
    return True
