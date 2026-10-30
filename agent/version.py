"""Single source for agent / worker release version (see repo VERSION file)."""

from __future__ import annotations

from pathlib import Path


def read_product_version() -> str:
    root = Path(__file__).resolve().parent.parent
    for candidate in (root / "VERSION", Path(__file__).resolve().parent / "VERSION"):
        if candidate.is_file():
            text = candidate.read_text(encoding="utf-8").strip()
            if text:
                return text.splitlines()[0].strip()
    return "0.0.0"


AGENT_VERSION = read_product_version()
