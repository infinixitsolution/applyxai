"""SSRF-safe URL checks before outbound fetch (Firecrawl still runs server-side; we block obvious unsafe targets)."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from backend.app.core.errors import AppError

_BLOCKED_SCHEMES = frozenset({"javascript", "file", "data", "blob", "ftp", "mailto", "tel"})


def _is_blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _resolve_host_ips(host: str) -> list[ipaddress._BaseAddress]:
    if not host:
        return []
    try:
        ip = ipaddress.ip_address(host)
        return [ip]
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError:
        return []
    ips: list[ipaddress._BaseAddress] = []
    for info in infos:
        try:
            ips.append(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue
    return ips


def is_url_safe_for_fetch(url: str, *, resolve_dns: bool = True) -> bool:
    raw = (url or "").strip()
    if not raw:
        return False
    try:
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    except Exception:
        return False
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return False
    if scheme in _BLOCKED_SCHEMES:
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    if host in ("localhost", "metadata.google.internal"):
        return False
    if host.endswith(".local") or host.endswith(".internal"):
        return False

    ips = _resolve_host_ips(host) if resolve_dns else []
    if not ips:
        try:
            ip = ipaddress.ip_address(host)
            ips = [ip]
        except ValueError:
            if resolve_dns:
                return False
            return True
    return all(not _is_blocked_ip(ip) for ip in ips)


def assert_url_safe_for_fetch(url: str) -> None:
    if not is_url_safe_for_fetch(url):
        raise AppError("UNSAFE_URL", "URL is not allowed for outbound fetch.", 400)
