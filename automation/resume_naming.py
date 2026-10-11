"""Resume file naming: {candidate}_{skills}_{experience}_v-{n}.ext"""

from __future__ import annotations

import re
from pathlib import Path

_VERSION_RE = re.compile(r"_v-(\d+)", re.IGNORECASE)


def slug(value: str, max_len: int = 48) -> str:
    text = re.sub(r"[^\w.-]+", "_", (value or "").strip())
    text = re.sub(r"_+", "_", text).strip("._")
    return (text[:max_len] if text else "Resume")


def format_experience(value: str | int | float | None) -> str:
    if value is None:
        return "0y"
    text = str(value).strip()
    if not text:
        return "0y"
    match = re.search(r"\d+", text)
    if match:
        return f"{match.group()}y"
    return slug(text, 12)


def format_skills(value: str | list | None, *, fallback: str = "") -> str:
    if isinstance(value, list):
        parts = [slug(str(item), 28) for item in value if str(item).strip()]
        if parts:
            return "-".join(parts[:4])
    if value and str(value).strip():
        raw = str(value).replace(",", " ").replace("/", " ")
        parts = [slug(p, 28) for p in raw.split() if p.strip()]
        if parts:
            return "-".join(parts[:4])
    return slug(fallback, 40) or "Skills"


def build_resume_stem(*, candidate: str, skills: str | list | None, experience: str | int | None) -> str:
    return f"{slug(candidate)}_{format_skills(skills)}_{format_experience(experience)}"


def build_resume_filename(
    *,
    candidate: str,
    skills: str | list | None,
    experience: str | int | None,
    version: int,
    ext: str,
) -> str:
    stem = build_resume_stem(candidate=candidate, skills=skills, experience=experience)
    suffix = ext if ext.startswith(".") else f".{ext}" if ext else ".pdf"
    name = f"{stem}_v-{max(1, int(version))}{suffix}"
    return name[:180]


def max_version_in_names(*names: str) -> int:
    best = 0
    for name in names:
        if not name:
            continue
        stem = Path(name).stem
        match = _VERSION_RE.search(stem)
        if match:
            best = max(best, int(match.group(1)))
    return best


def next_resume_version(*, cache_dir: str = "", extra_names: list[str] | None = None) -> int:
    """Next v-N across job cache files and optional known filenames (e.g. from DB)."""
    highest = max_version_in_names(*(extra_names or []))
    root = Path(cache_dir) / "jobs" if cache_dir else None
    if root is not None and root.is_dir():
        for path in root.rglob("*"):
            if path.is_file():
                highest = max(highest, max_version_in_names(path.name))
    return highest + 1
