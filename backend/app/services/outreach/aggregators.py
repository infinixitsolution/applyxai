"""Directory / aggregator hosts — not treated as an institute's official website."""

from __future__ import annotations

from urllib.parse import urlparse

_AGGREGATOR_SUFFIXES = (
    "justdial.com",
    "sulekha.com",
    "indiamart.com",
    "tradeindia.com",
    "shiksha.com",
    "collegedunia.com",
    "careers360.com",
    "mouthshut.com",
    "urbanpro.com",
    "learnpick.in",
    "highereducation.in",
    "getmyuni.com",
    "facebook.com",
    "fb.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "google.com",
    "bing.com",
    "yahoo.com",
)


def host_of(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower().removeprefix("www.")
    except Exception:
        return ""


def is_aggregator_host(host: str) -> bool:
    h = (host or "").lower().removeprefix("www.")
    if not h:
        return False
    return any(h == suffix or h.endswith("." + suffix) for suffix in _AGGREGATOR_SUFFIXES)


def is_aggregator_url(url: str) -> bool:
    return is_aggregator_host(host_of(url))


def looks_like_official_site(url: str) -> bool:
    host = host_of(url)
    if not host:
        return False
    if is_aggregator_host(host):
        return False
    lower = url.lower()
    if any(x in lower for x in ("/search", "/results?", "google.com/maps")):
        return False
    return True
