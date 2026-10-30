"""Minimal Firecrawl HTTP client for institute discovery."""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.services.outreach.url_safety import assert_url_safe_for_fetch

logger = logging.getLogger("applyxai.firecrawl")

_BASE = "https://api.firecrawl.dev/v1"
_TIMEOUT = 90.0


@dataclass
class FirecrawlSearchOutcome:
    ok: bool
    hits: list[dict[str, Any]] = field(default_factory=list)
    empty: bool = False
    error_code: str = ""
    error_message: str = ""
    malformed: bool = False


@dataclass
class FirecrawlScrapeOutcome:
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    error_code: str = ""
    error_message: str = ""
    http_status: int = 0


def _api_key(db: Session | None) -> str:
    from backend.app.services.platform_settings_service import get_effective_firecrawl_api_key

    key = get_effective_firecrawl_api_key(db)
    if not key:
        raise AppError(
            "FIRECRAWL_NOT_CONFIGURED",
            "Add a Firecrawl API key under Admin → Settings → Integrations, or set FIRECRAWL_API_KEY in .env.",
            503,
        )
    return key


def _headers(db: Session | None = None) -> dict[str, str]:
    key = _api_key(db)
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _normalize_search_hits(body: Any) -> list[dict[str, Any]]:
    """Firecrawl v1/v2 may return a list or a keyed object (e.g. web/news)."""
    if isinstance(body, list):
        return [h for h in body if isinstance(h, dict)]
    if not isinstance(body, dict):
        return []
    if body.get("success") is False:
        return []
    chunk = body.get("data")
    if chunk is None:
        chunk = body.get("results")
    if isinstance(chunk, list):
        return [h for h in chunk if isinstance(h, dict)]
    if isinstance(chunk, dict):
        out: list[dict[str, Any]] = []
        for value in chunk.values():
            if isinstance(value, list):
                out.extend(h for h in value if isinstance(h, dict))
            elif isinstance(value, dict):
                out.append(value)
        return out
    return []


def _parse_api_failure(body: Any, *, http_status: int) -> tuple[str, str]:
    if isinstance(body, dict):
        err = str(body.get("error") or body.get("message") or "").strip()
        if http_status in (401, 403):
            return "FIRECRAWL_AUTH", err or "Invalid Firecrawl API key."
        if http_status == 429:
            return "FIRECRAWL_RATE_LIMIT", err or "Firecrawl rate limit exceeded."
        if body.get("success") is False:
            return "FIRECRAWL_ERROR", err or "Firecrawl returned an error."
    if http_status >= 500:
        return "FIRECRAWL_ERROR", "Firecrawl service error."
    return "FIRECRAWL_ERROR", "Firecrawl request failed."


def search_web_with_outcome(query: str, *, limit: int = 10, db: Session | None = None) -> FirecrawlSearchOutcome:
    payload = {"query": query, "limit": min(limit, 20)}
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            resp = httpx.post(f"{_BASE}/search", json=payload, headers=_headers(db), timeout=_TIMEOUT)
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt < 2:
                time.sleep((0.4 * (2**attempt)) + random.uniform(0, 0.2))
                continue
            logger.warning("Firecrawl search failed: %s", exc)
            return FirecrawlSearchOutcome(
                ok=False,
                error_code="FIRECRAWL_ERROR",
                error_message="Web search failed. Check the Firecrawl key under Admin → Settings → Integrations.",
            )
        try:
            body = resp.json()
        except ValueError:
            return FirecrawlSearchOutcome(
                ok=False,
                malformed=True,
                error_code="FIRECRAWL_MALFORMED",
                error_message="Firecrawl returned invalid JSON.",
                http_status=resp.status_code,
            )
        if resp.status_code >= 400:
            code, msg = _parse_api_failure(body, http_status=resp.status_code)
            if resp.status_code == 429 and attempt < 2:
                time.sleep((0.6 * (2**attempt)) + random.uniform(0, 0.3))
                continue
            return FirecrawlSearchOutcome(ok=False, error_code=code, error_message=msg, http_status=resp.status_code)
        hits = _normalize_search_hits(body)
        if isinstance(body, dict) and body.get("success") is False:
            code, msg = _parse_api_failure(body, http_status=resp.status_code)
            return FirecrawlSearchOutcome(ok=False, error_code=code, error_message=msg, http_status=resp.status_code)
        return FirecrawlSearchOutcome(ok=True, hits=hits, empty=len(hits) == 0)
    if last_exc:
        return FirecrawlSearchOutcome(
            ok=False,
            error_code="FIRECRAWL_ERROR",
            error_message="Web search failed after retries.",
        )
    return FirecrawlSearchOutcome(ok=False, error_code="FIRECRAWL_ERROR", error_message="Web search failed.")


def search_web(query: str, *, limit: int = 10, db: Session | None = None) -> list[dict[str, Any]]:
    outcome = search_web_with_outcome(query, limit=limit, db=db)
    if not outcome.ok:
        if outcome.error_code == "FIRECRAWL_AUTH":
            raise AppError(outcome.error_code, outcome.error_message, 502)
        raise AppError(outcome.error_code or "FIRECRAWL_ERROR", outcome.error_message or "Web search failed.", 502)
    return outcome.hits


def scrape_url_with_outcome(url: str, *, db: Session | None = None) -> FirecrawlScrapeOutcome:
    try:
        assert_url_safe_for_fetch(url)
    except AppError as exc:
        return FirecrawlScrapeOutcome(ok=False, error_code=exc.code, error_message=exc.message)

    payload = {"url": url, "formats": ["markdown"]}
    for attempt in range(2):
        try:
            resp = httpx.post(f"{_BASE}/scrape", json=payload, headers=_headers(db), timeout=_TIMEOUT)
        except httpx.HTTPError as exc:
            logger.warning("Firecrawl scrape failed for %s: %s", url[:80], exc)
            if attempt == 0:
                time.sleep(0.3 + random.uniform(0, 0.2))
                continue
            return FirecrawlScrapeOutcome(
                ok=False,
                error_code="FIRECRAWL_ERROR",
                error_message="Page scrape failed.",
            )
        try:
            body = resp.json()
        except ValueError:
            return FirecrawlScrapeOutcome(
                ok=False,
                malformed=True,
                error_code="FIRECRAWL_MALFORMED",
                error_message="Firecrawl scrape returned invalid JSON.",
                http_status=resp.status_code,
            )
        if resp.status_code >= 400 or (isinstance(body, dict) and body.get("success") is False):
            code, msg = _parse_api_failure(body if isinstance(body, dict) else {}, http_status=resp.status_code)
            if resp.status_code == 429 and attempt == 0:
                time.sleep(0.5)
                continue
            return FirecrawlScrapeOutcome(ok=False, error_code=code, error_message=msg, http_status=resp.status_code)
        data = body.get("data") if isinstance(body, dict) else {}
        if not isinstance(data, dict):
            data = body if isinstance(body, dict) else {}
        return FirecrawlScrapeOutcome(ok=True, data=data, http_status=resp.status_code)
    return FirecrawlScrapeOutcome(ok=False, error_code="FIRECRAWL_ERROR", error_message="Page scrape failed.")


def scrape_url(url: str, *, db: Session | None = None) -> dict[str, Any]:
    outcome = scrape_url_with_outcome(url, db=db)
    if not outcome.ok:
        return {}
    return outcome.data


def verify_credentials(*, api_key: str | None = None, db: Session | None = None) -> dict[str, Any]:
    """Check API key validity via team credit usage (no scrape/search credits consumed)."""
    key = (api_key or "").strip()
    if not key:
        key = _api_key(db)
    headers = {"Authorization": f"Bearer {key}"}
    last_error: str | None = None
    for path in ("/v2/team/credit-usage", "/v1/team/credit-usage"):
        url = f"https://api.firecrawl.dev{path}"
        try:
            resp = httpx.get(url, headers=headers, timeout=30.0)
        except httpx.HTTPError as exc:
            logger.warning("Firecrawl verify failed: %s", exc)
            raise AppError("FIRECRAWL_ERROR", "Could not reach Firecrawl. Check your network and try again.", 502) from exc
        if resp.status_code in (401, 403):
            raise AppError("FIRECRAWL_AUTH", "Invalid Firecrawl API key.", 502)
        if resp.status_code == 404:
            continue
        if resp.status_code >= 500:
            last_error = resp.text[:200]
            continue
        try:
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise AppError("FIRECRAWL_ERROR", "Firecrawl rejected the request.", 502) from exc
        body = resp.json()
        if not body.get("success"):
            err = str(body.get("error") or "Firecrawl returned an error.")
            raise AppError("FIRECRAWL_ERROR", err, 502)
        data = body.get("data") or {}
        remaining = data.get("remainingCredits")
        plan = data.get("planCredits")
        message = "Firecrawl API key verified."
        if remaining is not None and plan is not None:
            message = f"Firecrawl API key verified — {remaining:,} of {plan:,} credits remaining this period."
        elif remaining is not None:
            message = f"Firecrawl API key verified — {remaining:,} credits remaining."
        return {"ok": True, "message": message, "remaining_credits": remaining, "plan_credits": plan}
    detail = last_error or "Could not verify the Firecrawl API key."
    raise AppError("FIRECRAWL_ERROR", detail, 502)
