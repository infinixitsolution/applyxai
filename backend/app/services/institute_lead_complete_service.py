"""Search and crawl public sources to fill in a single outreach lead profile."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.models.outreach import InstituteLead, InstituteLeadProfile, InstituteScrapeJob
from backend.app.services import firecrawl_client, institute_enrich_service
from backend.app.services.institute_scrape_service import (
    SOURCE_QUERY_SUFFIX,
    _snippet_list,
    check_scrape_prerequisites,
)

logger = logging.getLogger("applyxai.outreach.complete")

_COMPLETION_PLATFORMS = ("google", "facebook", "instagram", "linkedin")
_SEARCH_LIMIT = 6
_MAX_SCRAPE_URLS = 10
_SKIP_SCRAPE_SUBSTR = (
    "facebook.com",
    "fb.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "google.com/search",
)


def _host(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower().removeprefix("www.")
    except Exception:
        return ""


def _should_scrape(url: str) -> bool:
    lower = url.lower()
    if any(part in lower for part in _SKIP_SCRAPE_SUBSTR):
        return False
    if "/reel/" in lower or "/posts/" in lower or "/groups/" in lower:
        return False
    return bool(_host(url))


def _scrape_priority(url: str) -> int:
    host = _host(url)
    if not host:
        return 99
    if any(host.endswith(s) for s in (".edu.in", ".ac.in", ".edu")):
        return 0
    if host.endswith((".in", ".com", ".org", ".net")):
        return 1
    if "linkedin.com/company" in url.lower():
        return 2
    return 5


def complete_lead_profile(db: Session, lead: InstituteLead) -> dict[str, Any]:
    check_scrape_prerequisites(db)
    score_before = lead.completeness_score

    if lead.profile is None:
        lead.profile = InstituteLeadProfile(lead_id=lead.id)
        db.add(lead.profile)
        db.flush()

    existing = lead.profile.payload if isinstance(lead.profile.payload, dict) else {}
    emails_list = existing.get("emails") if isinstance(existing.get("emails"), list) else []
    phones_list = existing.get("phones") if isinstance(existing.get("phones"), list) else []
    name = (existing.get("name") or lead.display_name or "").strip()
    if not name:
        if emails_list:
            local = str(emails_list[0]).split("@", 1)[0]
            domain = str(emails_list[0]).split("@", 1)[-1].split(".")[0]
            name = (local if len(local) > 2 else domain).replace("-", " ").replace("_", " ").title()
        elif phones_list:
            name = f"Institute contact {phones_list[0]}"
        else:
            raise AppError("NOT_READY", "Add an institute name or a contact email/phone before completing the profile.", 422)

    addr = existing.get("address") if isinstance(existing.get("address"), dict) else {}
    city = str(addr.get("city") or "").strip()
    if not city and lead.job_id:
        job = db.get(InstituteScrapeJob, lead.job_id)
        if job and job.location:
            city = job.location.strip()

    base_query = name if not city else f"{name} {city}"
    snippets = _snippet_list(lead.profile.raw_snippets, "")
    scrape_urls: list[str] = []
    seen_urls: set[str] = set()
    searches_run = 0
    search_hits = 0
    scrapes_ok = 0
    scrapes_skipped = 0

    def _queue_url(url: str) -> None:
        u = url.strip()
        if not u or u in seen_urls:
            return
        seen_urls.add(u)
        scrape_urls.append(u)

    if lead.source_url:
        _queue_url(lead.source_url)
    website = str(existing.get("website") or "").strip()
    if website:
        _queue_url(website)

    extra_queries = [
        f"{base_query} training institute contact email phone",
        f"{base_query} official website",
        f'"{name}" {city} institute'.strip(),
    ]
    for em in emails_list[:2]:
        em = str(em).strip()
        if em:
            extra_queries.append(f"{em} training institute contact")
    for ph in phones_list[:2]:
        ph = str(ph).strip()
        if ph:
            extra_queries.append(f"{ph} coaching institute india contact")

    for search_q in extra_queries:
        if not search_q.strip():
            continue
        try:
            hits = firecrawl_client.search_web(search_q, limit=_SEARCH_LIMIT, db=db)
            searches_run += 1
        except AppError as exc:
            if exc.code == "FIRECRAWL_NOT_CONFIGURED":
                raise
            logger.warning("Profile completion search skipped: %s", exc.message)
            continue
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            search_hits += 1
            url = str(hit.get("url") or hit.get("link") or "").strip()
            snippet = str(hit.get("description") or hit.get("snippet") or hit.get("markdown") or "")
            markdown = str(hit.get("markdown") or "")
            if markdown and len(markdown) > 80:
                snippet = f"{snippet}\n{markdown}" if snippet else markdown
            if snippet and snippet not in snippets:
                snippets.append(snippet[:8000])
            if url:
                _queue_url(url)

    for platform in _COMPLETION_PLATFORMS:
        suffix = SOURCE_QUERY_SUFFIX.get(platform, "")
        search_q = f"{base_query}{suffix} training institute"
        try:
            hits = firecrawl_client.search_web(search_q, limit=_SEARCH_LIMIT, db=db)
            searches_run += 1
        except AppError as exc:
            if exc.code == "FIRECRAWL_NOT_CONFIGURED":
                raise
            logger.warning("Profile completion search skipped (%s): %s", platform, exc.message)
            continue

        for hit in hits:
            if not isinstance(hit, dict):
                continue
            search_hits += 1
            url = str(hit.get("url") or hit.get("link") or "").strip()
            snippet = str(hit.get("description") or hit.get("snippet") or hit.get("markdown") or "")
            if snippet and snippet not in snippets:
                snippets.append(snippet[:4000])
            if url:
                _queue_url(url)

    scrape_urls.sort(key=_scrape_priority)
    to_scrape = [u for u in scrape_urls if _should_scrape(u)][:_MAX_SCRAPE_URLS]
    scrapes_skipped = max(0, len(scrape_urls) - len(to_scrape))

    for url in to_scrape:
        scraped = firecrawl_client.scrape_url(url, db=db)
        markdown = str(scraped.get("markdown") or scraped.get("content") or "")
        if markdown:
            scrapes_ok += 1
            if markdown not in snippets:
                snippets.append(markdown[:8000])

    if not snippets:
        raise AppError(
            "NOT_FOUND",
            "No public content found. Edit the institute name or add city under Edit profile, then try again.",
            404,
        )

    lead.profile.raw_snippets = snippets[-20:]
    primary_url = lead.source_url or website or (to_scrape[0] if to_scrape else "")

    try:
        new_payload, confidence = institute_enrich_service.enrich_from_snippets(
            db,
            title=name,
            url=primary_url,
            snippets=snippets[-20:],
            complete=True,
        )
    except AppError as exc:
        if exc.code == "AI_DISABLED":
            raise AppError(
                "AI_DISABLED",
                "Platform AI is required to complete profiles. Enable it under Admin → Settings → AI.",
                503,
            ) from exc
        raise

    merged = institute_enrich_service.merge_profiles(existing, new_payload)
    blob = "\n\n".join(snippets[-20:])
    extracted = institute_enrich_service.extract_contacts_from_text(blob)
    for email in extracted.get("emails") or []:
        if email not in merged["emails"]:
            merged["emails"].append(email)
    merged["emails"] = merged["emails"][:5]
    for phone in extracted.get("phones") or []:
        if phone not in merged["phones"]:
            merged["phones"].append(phone)
    merged["phones"] = merged["phones"][:5]
    if not str(merged.get("website") or "").strip():
        if extracted.get("websites"):
            merged["website"] = extracted["websites"][0]
        elif primary_url:
            merged["website"] = primary_url

    lead.profile.payload = merged
    lead.profile.confidence = confidence
    lead.display_name = (merged.get("name") or lead.display_name or name)[:190]
    institute_enrich_service.sync_lead_completeness_score(lead)
    if lead.completeness_score >= 40:
        lead.status = "enriched"
    elif lead.status == "completing_profile":
        lead.status = "discovered"
    db.flush()

    score_after = lead.completeness_score
    hints: list[str] = []
    if not merged.get("emails"):
        hints.append("No email found — add one manually or refine the institute name/city.")
    if not merged.get("phones"):
        hints.append("No phone found in public listings.")
    if scrapes_ok == 0 and search_hits > 0:
        hints.append("Search returned snippets but institute pages could not be scraped (often social/login walls).")
    if score_after <= score_before:
        hints.append("Score did not improve; sources may not list contact details publicly.")

    summary = {
        "score_before": score_before,
        "score_after": score_after,
        "searches_run": searches_run,
        "search_hits": search_hits,
        "urls_scraped": scrapes_ok,
        "urls_skipped": scrapes_skipped,
        "snippets_used": min(len(snippets), 20),
        "hints": hints,
    }
    return {"lead": lead, "completion": summary}
