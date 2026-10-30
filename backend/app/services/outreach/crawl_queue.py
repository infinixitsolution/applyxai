"""Prioritized crawl URL selection for institute pages."""

from __future__ import annotations

from backend.app.services.outreach.aggregators import host_of, is_aggregator_url
from backend.app.services.outreach.url_normalize import normalize_url_for_compare
from backend.app.services.outreach.url_safety import is_url_safe_for_fetch

_SKIP_SUBSTR = (
    "/reel/",
    "/posts/",
    "/groups/",
    "/watch?",
    "google.com/search",
    "facebook.com/sharer",
)

_CONTACT_PATH_HINTS = ("contact", "about", "admission", "course", "program", "location", "branch", "faculty", "reach-us")
_HOME_HINTS = ("", "/", "/home", "/index")


def should_scrape_url(url: str) -> bool:
    lower = url.lower()
    if not is_url_safe_for_fetch(url, resolve_dns=False):
        return False
    if any(part in lower for part in _SKIP_SUBSTR):
        return False
    if is_aggregator_url(url):
        return True  # listing page may contain official website link
    return bool(host_of(url))


def scrape_priority(url: str) -> int:
    lower = url.lower()
    host = host_of(url)
    if not host:
        return 99
    if is_aggregator_url(url):
        return 8
    if any(h in lower for h in _CONTACT_PATH_HINTS):
        return 0
    if any(host.endswith(s) for s in (".edu.in", ".ac.in", ".edu")):
        return 1
    path = lower.split(host, 1)[-1] if host in lower else lower
    if path in _HOME_HINTS or path.endswith("/"):
        return 2
    if host.endswith((".in", ".com", ".org", ".net")):
        return 3
    if "linkedin.com/company" in lower:
        return 4
    return 6


def build_crawl_queue(
    *,
    discovery_url: str,
    extra_urls: list[str],
    official_website: str = "",
    max_pages: int,
) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    def add(u: str) -> None:
        clean = u.strip()
        if not clean or not should_scrape_url(clean):
            return
        key = normalize_url_for_compare(clean)
        if not key or key in seen:
            return
        seen.add(key)
        ordered.append(clean)

    if official_website:
        add(official_website)
        base = official_website.rstrip("/")
        for suffix in ("/contact", "/contact-us", "/about", "/about-us", "/courses", "/admissions"):
            add(base + suffix)
    add(discovery_url)
    for u in extra_urls:
        add(u)

    ordered.sort(key=scrape_priority)
    return ordered[:max_pages]
