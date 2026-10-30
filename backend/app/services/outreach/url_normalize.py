"""Normalize URLs for comparison, deduplication, and storage."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "gclid",
        "fbclid",
        "mc_cid",
        "mc_eid",
        "ref",
        "ref_src",
    }
)


def _strip_default_port(scheme: str, netloc: str) -> str:
    if scheme == "https" and netloc.endswith(":443"):
        return netloc[:-4]
    if scheme == "http" and netloc.endswith(":80"):
        return netloc[:-3]
    return netloc


def normalize_url_for_storage(url: str) -> str:
    """Preserve original URL with light cleanup for DB storage."""
    clean = (url or "").strip()
    if not clean:
        return ""
    if not clean.startswith(("http://", "https://")):
        clean = "https://" + clean.lstrip("/")
    return clean[:2000]


def normalize_url_for_compare(url: str) -> str:
    """Canonical form for dedupe and identity (no fragment, no tracking params)."""
    raw = normalize_url_for_storage(url)
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
    except Exception:
        return raw.lower().rstrip("/")

    scheme = (parsed.scheme or "https").lower()
    if scheme not in ("http", "https"):
        return ""

    netloc = (parsed.netloc or "").lower()
    if not netloc and parsed.path:
        netloc = parsed.path.split("/")[0].lower()
    netloc = netloc.removeprefix("www.")
    netloc = _strip_default_port(scheme, netloc)

    path = parsed.path or "/"
    path = re.sub(r"/+", "/", path)
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    query_pairs = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
    ]
    query = urlencode(sorted(query_pairs)) if query_pairs else ""

    return urlunparse((scheme, netloc, path, "", query, ""))


def url_identity_key(url: str) -> str:
    """Path-aware key suitable for listing URLs on aggregator domains."""
    norm = normalize_url_for_compare(url)
    if not norm:
        return ""
    parsed = urlparse(norm)
    host = (parsed.netloc or "").lower()
    path = parsed.path or "/"
    return f"{host}{path}"[:480]
