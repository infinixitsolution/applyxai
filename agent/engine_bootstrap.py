"""Run runAiBot.py when frozen PyInstaller builds cannot execute a .py script path."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

ENGINE_FLAG = "--applyxai-engine"


def engine_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def engine_script() -> Path:
    return engine_root() / "runAiBot.py"


def frozen_engine_executable() -> str:
    """Prefer the CLI exe when the GUI exe would otherwise spawn itself."""
    exe = Path(sys.executable)
    if getattr(sys, "frozen", False) and "GUI" in exe.stem.upper():
        cli = exe.with_name("ApplyXAI-Agent.exe")
        if cli.is_file():
            return str(cli)
    return sys.executable


def engine_argv() -> list[str]:
    if getattr(sys, "frozen", False):
        return [frozen_engine_executable(), ENGINE_FLAG]
    return [sys.executable, str(engine_script())]


def run_engine_child_if_requested() -> bool:
    """If argv contains ENGINE_FLAG, run runAiBot and return True."""
    if ENGINE_FLAG not in sys.argv:
        return False
    sys.argv = [a for a in sys.argv if a != ENGINE_FLAG]
    script = engine_script()
    if not script.is_file():
        print(f"Automation engine missing from bundle: {script}", file=sys.stderr)
        raise SystemExit(1)
    runpy.run_path(str(script), run_name="__main__")
    return True
