"""Paths to bundled mascot / icon assets (dev tree and PyInstaller)."""

from __future__ import annotations

import sys
from pathlib import Path


def _agent_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def mascot_png() -> Path:
    return _agent_root() / "branding" / "mascot.png"


def window_icon_ico() -> Path:
    return _agent_root() / "branding" / "applyxai.ico"
