"""Deterministic search query generation for institute discovery."""

from __future__ import annotations

import re

SOURCE_QUERY_SUFFIX = {
    "google": "",
    "facebook": " site:facebook.com",
    "instagram": " site:instagram.com",
    "linkedin": " site:linkedin.com",
}

_INSTITUTE_PHRASES = (
    "training institute",
    "coaching centre",
    "coaching center",
    "training center",
    "training centre",
)


def _query_already_has_institute_phrase(text: str) -> bool:
    lower = text.lower()
    return any(p in lower for p in _INSTITUTE_PHRASES)


def _base_keyword_query(keyword: str, location: str) -> str:
    kw = re.sub(r"\s+", " ", (keyword or "").strip())
    loc = re.sub(r"\s+", " ", (location or "").strip())
    parts = [p for p in (kw, loc) if p]
    base = " ".join(parts)
    if not base:
        return "training institute"
    if not _query_already_has_institute_phrase(base):
        base = f"{base} training institute"
    return base


def build_search_queries(
    *,
    keyword: str,
    location: str,
    sources: list[str],
    max_queries: int,
) -> list[tuple[str, str]]:
    """Return (platform, query) pairs, capped at max_queries."""
    base = _base_keyword_query(keyword, location)
    platforms = sources or ["google"]
    out: list[tuple[str, str]] = []
    for platform in platforms:
        suffix = SOURCE_QUERY_SUFFIX.get(platform, "")
        out.append((platform, f"{base}{suffix}".strip()))
    if len(out) > max_queries:
        return out[:max_queries]
    extras: list[tuple[str, str]] = []
    if location and "google" in platforms:
        extras.append(("google", f"{keyword.strip()} {location.strip()} contact email phone".strip()))
    for item in extras:
        if len(out) >= max_queries:
            break
        if item not in out:
            out.append(item)
    return out[:max_queries]
