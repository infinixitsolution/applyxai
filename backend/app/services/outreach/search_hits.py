"""Normalize Firecrawl search hits into discovery records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.services.outreach.url_normalize import normalize_url_for_compare, normalize_url_for_storage
from backend.app.services.outreach.url_safety import is_url_safe_for_fetch


@dataclass
class DiscoveryHit:
    url: str
    original_url: str
    title: str
    snippet: str
    platform: str = "google"
    metadata: dict[str, Any] = field(default_factory=dict)


def _hit_url(raw: dict[str, Any]) -> str:
    for key in ("url", "link", "sourceURL", "source_url"):
        val = raw.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _hit_snippet(raw: dict[str, Any]) -> str:
    for key in ("description", "snippet", "markdown", "content"):
        val = raw.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def normalize_firecrawl_hits(
    hits: list[dict[str, Any]],
    *,
    platform: str,
) -> list[DiscoveryHit]:
    seen: set[str] = set()
    out: list[DiscoveryHit] = []
    for raw in hits:
        if not isinstance(raw, dict):
            continue
        original = _hit_url(raw)
        if not original:
            continue
        stored = normalize_url_for_storage(original)
        if not stored.startswith(("http://", "https://")):
            continue
        if not is_url_safe_for_fetch(stored, resolve_dns=False):
            continue
        key = normalize_url_for_compare(stored)
        if not key or key in seen:
            continue
        seen.add(key)
        title = str(raw.get("title") or raw.get("name") or "").strip()
        snippet = _hit_snippet(raw)
        out.append(
            DiscoveryHit(
                url=stored,
                original_url=original,
                title=title,
                snippet=snippet,
                platform=platform,
                metadata={"compare_key": key},
            )
        )
    return out
