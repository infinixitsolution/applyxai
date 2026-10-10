"""Compare local agent version with the server's /api/site/agent-release."""

from __future__ import annotations

import logging
from urllib.parse import urljoin

import httpx

logger = logging.getLogger("applyxai.agent.update")


def _parse_version(raw: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in (raw or "").strip().split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            break
    return tuple(parts) if parts else (0,)


def newer_available(server: str, current: str, *, timeout: float = 8.0) -> dict | None:
    url = urljoin(server.rstrip("/") + "/", "api/site/agent-release")
    try:
        resp = httpx.get(url, timeout=timeout, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json().get("data") or {}
    except Exception as exc:
        logger.debug("Agent release check failed: %s", exc)
        return None
    remote = str(data.get("version") or "").strip()
    if not remote or _parse_version(remote) <= _parse_version(current):
        return None
    return {"version": remote, "download_url": str(data.get("download_url") or "").strip()}
