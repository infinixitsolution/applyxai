"""
Search the public web (Firecrawl) for HR contacts and job links when a company appears in automation.
"""

from __future__ import annotations

import logging
import re
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from automation.company_contacts import contact_key, extract_published_contacts, merge_contacts
from backend.app.core.errors import AppError
from backend.app.models import CompanyDirectoryProfile
from backend.app.services import firecrawl_client

logger = logging.getLogger("applyxai.company_directory")

_STATUS_IDLE, _STATUS_RUNNING, _STATUS_READY, _STATUS_FAILED = "idle", "running", "ready", "failed"
ENRICH_COOLDOWN = timedelta(days=7)
_MAX_QUERIES = 3
_MAX_HITS = 5
_MAX_SCRAPES = 10

_JOB_URL = re.compile(
    r"https?://(?:[\w.-]+\.)?(?:linkedin\.com/jobs/view/[\w-]+|naukri\.com/[\w/-]*job[\w/-]*|"
    r"boards\.greenhouse\.io/[\w./-]+|jobs\.lever\.co/[\w./-]+|careers\.[\w.-]+/[\w./-]+)",
    re.I,
)
_HR_HINT = re.compile(r"\b(recruiter|talent|hiring|human resources|hr\b|people ops|staffing)\b", re.I)


def company_key(name: str) -> str:
    return " ".join(str(name or "").strip().lower().split())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_profile(db: Session, name: str) -> CompanyDirectoryProfile | None:
    key = company_key(name)
    if not key:
        return None
    return db.scalar(select(CompanyDirectoryProfile).where(CompanyDirectoryProfile.company_key == key))


def get_or_create_profile(db: Session, name: str) -> CompanyDirectoryProfile:
    key = company_key(name)
    display = str(name or "").strip()[:255]
    row = get_profile(db, name)
    if row is not None:
        if display and row.company_name != display:
            row.company_name = display
        return row
    row = CompanyDirectoryProfile(company_key=key, company_name=display, status=_STATUS_IDLE)
    db.add(row)
    db.flush()
    return row


def _firecrawl_ready(db: Session) -> bool:
    try:
        from backend.app.services.platform_settings_service import get_effective_firecrawl_api_key

        return bool(get_effective_firecrawl_api_key(db))
    except Exception:
        return False


def schedule_enrichment(company_name: str, *, force: bool = False) -> None:
    """Queue web profiling for a new company (no-op if Firecrawl is not configured)."""
    name = str(company_name or "").strip()
    if len(name) < 2:
        return

    def _dispatch() -> None:
        from backend.app.core.database import SessionLocal

        with SessionLocal() as db:
            if not _firecrawl_ready(db):
                return
            profile = get_or_create_profile(db, name)
            if not force:
                if profile.status == _STATUS_RUNNING:
                    db.commit()
                    return
                if profile.last_enriched_at and _now() - profile.last_enriched_at < ENRICH_COOLDOWN:
                    db.commit()
                    return
            profile.status = _STATUS_RUNNING
            profile.error_message = ""
            db.commit()
            key = profile.company_key

        try:
            from backend.app.worker import run_company_directory_enrichment

            run_company_directory_enrichment.delay(key)
        except Exception:
            threading.Thread(
                target=_run_enrichment_sync,
                args=(key,),
                name=f"company-enrich-{key[:24]}",
                daemon=True,
            ).start()

    threading.Thread(target=_dispatch, name="company-enrich-schedule", daemon=True).start()


def _run_enrichment_sync(company_key_value: str) -> None:
    from backend.app.core.database import SessionLocal

    with SessionLocal() as db:
        try:
            enrich_profile(db, company_key_value)
            db.commit()
        except Exception:
            logger.exception("Company directory enrichment failed for %s", company_key_value)
            db.rollback()
            profile = db.scalar(
                select(CompanyDirectoryProfile).where(CompanyDirectoryProfile.company_key == company_key_value)
            )
            if profile is not None:
                profile.status = _STATUS_FAILED
                profile.error_message = "Profiling failed. Try again from the company page."
                db.commit()


def _search_queries(company: str) -> list[str]:
    quoted = company.strip()
    return [
        f'"{quoted}" recruiter email OR hiring contact',
        f'"{quoted}" HR talent acquisition contact phone',
        f'"{quoted}" careers jobs apply site:linkedin.com OR site:naukri.com',
    ][: _MAX_QUERIES]


def _hit_url(hit: dict[str, Any]) -> str:
    for field in ("url", "link", "sourceURL"):
        value = str(hit.get(field) or "").strip()
        if value.startswith("http"):
            return value
    return ""


def _hit_title(hit: dict[str, Any]) -> str:
    return str(hit.get("title") or hit.get("metadata", {}).get("title") or "")[:300]


def _hit_snippet(hit: dict[str, Any]) -> str:
    parts = [hit.get("description"), hit.get("snippet"), hit.get("markdown")]
    meta = hit.get("metadata") if isinstance(hit.get("metadata"), dict) else {}
    parts.append(meta.get("description"))
    return "\n".join(str(p) for p in parts if p)[:50_000]


def _extract_job_links(text: str, page_url: str) -> list[dict]:
    found: dict[str, dict] = {}
    for match in _JOB_URL.finditer(text or ""):
        url = match.group(0).split("?")[0].rstrip("/")
        if url not in found:
            found[url] = {"url": url[:1024], "title": "", "source_url": page_url[:1024]}
    if page_url and _JOB_URL.search(page_url):
        clean = page_url.split("?")[0]
        if clean not in found:
            found[clean] = {"url": clean[:1024], "title": "", "source_url": clean[:1024]}
    return list(found.values())


def _contacts_from_page(text: str, *, page_url: str, page_title: str) -> list[dict]:
    rows = extract_published_contacts(text)
    out: list[dict] = []
    for row in rows:
        enriched = {**row, "sources": [{"url": page_url[:1024], "title": page_title[:300]}]}
        if _HR_HINT.search(text) and not enriched.get("role"):
            enriched["role"] = "Recruiting / HR (inferred from page)"
        out.append(enriched)
    return out


def _merge_directory_contacts(*groups: list) -> list[dict]:
    merged: dict[str, dict] = {}
    order: list[str] = []
    for group in groups:
        for raw in group or []:
            if not isinstance(raw, dict):
                continue
            base = {k: str(raw.get(k) or "")[:500] for k in ("name", "email", "phone", "role", "link")}
            key = contact_key(base)
            if not key:
                continue
            sources = raw.get("sources") if isinstance(raw.get("sources"), list) else []
            current = merged.get(key)
            if current is None:
                merged[key] = {**base, "sources": list(sources)}
                order.append(key)
                continue
            for field in ("name", "email", "phone", "role", "link"):
                if not current[field] and base[field]:
                    current[field] = base[field]
            for src in sources:
                if isinstance(src, dict) and src.get("url") and src not in current["sources"]:
                    current["sources"].append(src)
    return [merged[k] for k in order]


def enrich_profile(db: Session, key_or_name: str) -> CompanyDirectoryProfile:
    key = company_key(key_or_name)
    profile = db.scalar(select(CompanyDirectoryProfile).where(CompanyDirectoryProfile.company_key == key))
    if profile is None:
        profile = get_or_create_profile(db, key_or_name)
    company = profile.company_name or key_or_name
    profile.status = _STATUS_RUNNING
    profile.error_message = ""
    db.flush()

    if not _firecrawl_ready(db):
        profile.status = _STATUS_FAILED
        profile.error_message = "Add a Firecrawl API key under Admin → Settings → Integrations."
        return profile

    seen_urls: set[str] = set()
    contacts: list[dict] = []
    job_links: dict[str, dict] = {}
    source_pages: list[dict] = []
    scrape_budget = _MAX_SCRAPES

    for query in _search_queries(company):
        try:
            hits = firecrawl_client.search_web(query, limit=_MAX_HITS, db=db)
        except AppError as exc:
            profile.status = _STATUS_FAILED
            profile.error_message = exc.message[:2000]
            return profile
        for hit in hits:
            url = _hit_url(hit)
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            title = _hit_title(hit)
            snippet = _hit_snippet(hit)
            contacts.extend(_contacts_from_page(snippet, page_url=url, page_title=title))
            for link in _extract_job_links(snippet, url):
                job_links[link["url"]] = link
            if scrape_budget <= 0:
                continue
            scrape_budget -= 1
            data = firecrawl_client.scrape_url(url, db=db)
            markdown = str(data.get("markdown") or data.get("content") or "")
            meta = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
            page_title = str(meta.get("title") or title)[:300]
            source_pages.append({"url": url[:1024], "title": page_title})
            contacts.extend(_contacts_from_page(markdown, page_url=url, page_title=page_title))
            for link in _extract_job_links(markdown, url):
                job_links[link["url"]] = link

    profile.contacts = _merge_directory_contacts(contacts)
    profile.job_links = sorted(job_links.values(), key=lambda row: row["url"])[:50]
    profile.source_pages = source_pages[:30]
    profile.last_enriched_at = _now()
    profile.status = _STATUS_READY if profile.contacts or profile.job_links else _STATUS_READY
    if not profile.contacts and not profile.job_links:
        profile.error_message = "No public HR contacts or job links found yet. Try again later or add jobs from automation."
    return profile


def profiling_snapshot(profile: CompanyDirectoryProfile | None) -> dict:
    if profile is None:
        return {"status": _STATUS_IDLE, "last_enriched_at": None, "error": "", "sources_scraped": 0}
    return {
        "status": profile.status,
        "last_enriched_at": profile.last_enriched_at.isoformat() if profile.last_enriched_at else None,
        "error": (profile.error_message or "")[:500],
        "sources_scraped": len(profile.source_pages or []),
    }


def directory_contacts_for_api(profile: CompanyDirectoryProfile | None) -> list[dict]:
    if profile is None:
        return []
    out: list[dict] = []
    for row in profile.contacts or []:
        if not isinstance(row, dict):
            continue
        out.append({
            "name": str(row.get("name") or ""),
            "email": str(row.get("email") or ""),
            "phone": str(row.get("phone") or ""),
            "role": str(row.get("role") or ""),
            "link": str(row.get("link") or ""),
            "sources": row.get("sources") if isinstance(row.get("sources"), list) else [],
            "jobs": [],
        })
    return out
