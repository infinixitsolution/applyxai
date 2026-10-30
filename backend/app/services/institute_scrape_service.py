"""Run institute discovery jobs via Firecrawl search + prioritized scrape."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.app.core.config import settings
from backend.app.core.errors import AppError
from backend.app.models.outreach import InstituteLead, InstituteLeadProfile, InstituteScrapeJob
from backend.app.services import firecrawl_client, institute_enrich_service
from backend.app.services.firecrawl_client import FirecrawlScrapeOutcome, FirecrawlSearchOutcome
from backend.app.services.outreach.aggregators import is_aggregator_url, looks_like_official_site
from backend.app.services.outreach.contact_extract import extract_contacts_from_content
from backend.app.services.outreach.crawl_queue import build_crawl_queue
from backend.app.services.outreach.evidence import apply_evidence_gate, merge_lead_payload
from backend.app.services.outreach.identity import (
    discovery_dedupe_key,
    find_matching_lead,
    merge_identity_keys_on_official_site,
)
from backend.app.services.outreach.scrape_config import budgets
from backend.app.services.outreach.search_hits import normalize_firecrawl_hits
from backend.app.services.outreach import search_queries as outreach_search_queries
from backend.app.services.outreach.search_queries import build_search_queries
from backend.app.services.platform_settings_service import get_effective_ai, get_effective_firecrawl_api_key

logger = logging.getLogger("applyxai.outreach.scrape")

# Backward-compatible export for institute_lead_complete_service
SOURCE_QUERY_SUFFIX = outreach_search_queries.SOURCE_QUERY_SUFFIX


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _empty_stats() -> dict[str, Any]:
    return {
        "search_queries_run": 0,
        "search_results": 0,
        "unique_candidate_urls": 0,
        "pages_attempted": 0,
        "pages_scraped": 0,
        "pages_failed": 0,
        "candidates_seen": 0,
        "leads_created": 0,
        "leads_updated": 0,
        "duplicates_skipped": 0,
        "contacts_extracted": 0,
        "contacts_syntax_valid": 0,
        "profiles_enriched": 0,
        "profiles_needs_review": 0,
        "firecrawl_errors": [],
        "partial": False,
    }


def _snippet_list(raw: list | str | None, fallback: str) -> list[str]:
    if isinstance(raw, list):
        parts = [str(s).strip() for s in raw if str(s).strip()]
        if parts:
            return parts
    elif isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    fb = fallback.strip()
    return [fb] if fb else []


def _append_raw_snippet(profile: InstituteLeadProfile | None, text: str, *, limit: int = 4000) -> bool:
    chunk = (text or "").strip()
    if not chunk or profile is None:
        return False
    snippets = [str(s).strip() for s in (profile.raw_snippets or []) if str(s).strip()]
    normalized = chunk[:limit]
    if any(normalized in s or s in normalized for s in snippets):
        return False
    snippets.append(normalized)
    profile.raw_snippets = snippets[-20:]
    return True


def _record_source_url(lead: InstituteLead, url: str, platform: str) -> bool:
    clean = (url or "").strip()[:2000]
    if not clean:
        return False
    changed = False
    if not (lead.source_url or "").strip():
        lead.source_url = clean
        return True
    if clean == lead.source_url:
        return False
    if lead.profile is None:
        return False
    payload = dict(lead.profile.payload if isinstance(lead.profile.payload, dict) else {})
    social = dict(payload.get("social") if isinstance(payload.get("social"), dict) else {})
    platform_key = platform if platform in social else ""
    if platform_key and not str(social.get(platform_key) or "").strip():
        social[platform_key] = clean
        payload["social"] = social
        lead.profile.payload = payload
        changed = True
    sources = payload.get("source_urls") if isinstance(payload.get("source_urls"), list) else []
    if clean not in sources:
        sources.append(clean)
        payload["source_urls"] = sources[-15:]
        lead.profile.payload = payload
        changed = True
    return changed


def _dedupe_key(url: str, title: str) -> str:
    return discovery_dedupe_key(url, title)


def _extract_official_website_from_text(text: str) -> str:
    from backend.app.services.institute_enrich_service import _WEBSITE_RE

    for match in _WEBSITE_RE.finditer(text or ""):
        url = match.group(0).rstrip(".,)")
        if looks_like_official_site(url):
            return url
    return ""


def check_scrape_prerequisites(db: Session) -> None:
    if not get_effective_firecrawl_api_key(db):
        raise AppError(
            "FIRECRAWL_NOT_CONFIGURED",
            "Add a Firecrawl API key under Admin → Settings → Integrations, then run Test API key.",
            503,
        )
    ai = get_effective_ai(db)
    if not ai.feature_on("outreach"):
        raise AppError(
            "AI_DISABLED",
            "Enable Platform AI under Admin → Settings → AI: turn it on, save an API key, and enable "
            "Institute outreach enrichment.",
            503,
        )


def create_job(
    db: Session,
    *,
    admin_user_id: uuid.UUID | None,
    query: str,
    location: str,
    sources: list[str],
    max_results: int,
    owner_institute_id=None,
) -> InstituteScrapeJob:
    cap = min(max_results, settings.OUTREACH_MAX_LEADS_PER_JOB)
    job = InstituteScrapeJob(
        created_by_user_id=admin_user_id,
        owner_institute_id=owner_institute_id,
        query=query,
        location=location.strip(),
        sources=sources,
        max_results=cap,
        status="queued",
        stats=_empty_stats(),
    )
    db.add(job)
    db.flush()
    return job


def recover_stale_scrape_jobs(db: Session, *, max_age_minutes: int | None = None, max_jobs: int = 1) -> int:
    """Re-run jobs stuck in queued (worker never picked up). Returns count recovered."""
    age = max_age_minutes or budgets().stale_queued_job_minutes
    cutoff = _now() - timedelta(minutes=age)
    stale = db.scalars(
        select(InstituteScrapeJob)
        .where(
            InstituteScrapeJob.status == "queued",
            InstituteScrapeJob.created_at < cutoff,
        )
        .limit(max(1, max_jobs))
    ).all()
    count = 0
    for job in stale:
        logger.warning("Recovering stale queued scrape job %s", job.id)
        run_scrape_job(db, job.id)
        count += 1
    return count


def _upsert_lead(
    db: Session,
    *,
    job: InstituteScrapeJob,
    platform: str,
    url: str,
    title: str,
    snippet: str,
    city: str,
    official_website: str = "",
) -> tuple[InstituteLead, bool, bool]:
    """Return (lead, created, new_content)."""
    key = discovery_dedupe_key(url, title)
    existing, match_reason = find_matching_lead(
        db,
        dedupe_key=key,
        discovery_url=url,
        title=title,
        official_website=official_website,
        city=city,
    )
    if existing is None:
        existing = db.scalar(
            select(InstituteLead).options(joinedload(InstituteLead.profile)).where(InstituteLead.dedupe_key == key)
        )

    if existing is not None:
        if existing.job_id is None:
            existing.job_id = job.id
        if existing.profile is None:
            existing.profile = InstituteLeadProfile(lead_id=existing.id, raw_snippets=[])
            db.add(existing.profile)
            db.flush()
        new_content = _append_raw_snippet(existing.profile, snippet)
        new_content = _record_source_url(existing, url, platform) or new_content
        if title and not (existing.display_name or "").strip():
            existing.display_name = title[:190]
            new_content = True
        if official_website and merge_identity_keys_on_official_site(existing, website=official_website, name=title):
            new_content = True
        return existing, False, new_content

    lead = InstituteLead(
        job_id=job.id,
        owner_institute_id=getattr(job, "owner_institute_id", None),
        source_platform=platform,
        source_url=url[:2000],
        dedupe_key=key,
        display_name=(title or "")[:190],
        status="discovered",
    )
    db.add(lead)
    db.flush()
    profile = InstituteLeadProfile(lead_id=lead.id, raw_snippets=[snippet[:4000]] if snippet else [])
    db.add(profile)
    db.flush()
    return lead, True, True


def _crawl_institute_pages(
    db: Session,
    *,
    discovery_url: str,
    official_website: str,
    snippets: list[str],
    stats: dict[str, Any],
    pages_budget: int,
) -> tuple[list[str], list[Any], str]:
    """Scrape prioritized URLs; return updated snippets, contact candidates, resolved official site."""
    budget = budgets()
    queue = build_crawl_queue(
        discovery_url=discovery_url,
        extra_urls=[],
        official_website=official_website,
        max_pages=min(budget.max_pages_per_institute, pages_budget),
    )
    all_candidates: list[Any] = []
    resolved_site = official_website
    for page_url in queue:
        if stats["pages_attempted"] >= pages_budget:
            break
        stats["pages_attempted"] += 1
        outcome: FirecrawlScrapeOutcome = firecrawl_client.scrape_url_with_outcome(page_url, db=db)
        if not outcome.ok:
            stats["pages_failed"] += 1
            if outcome.error_message:
                stats["firecrawl_errors"].append(outcome.error_message[:200])
            continue
        stats["pages_scraped"] += 1
        markdown = str(outcome.data.get("markdown") or outcome.data.get("content") or "")
        if not markdown:
            continue
        snippets.append(markdown[: budget.max_markdown_chars])
        candidates = extract_contacts_from_content(markdown, source_url=page_url)
        all_candidates.extend(candidates)
        if not resolved_site:
            resolved_site = _extract_official_website_from_text(markdown)
    return snippets, all_candidates, resolved_site


def run_scrape_job(db: Session, job_id: uuid.UUID) -> None:
    job = db.get(InstituteScrapeJob, job_id)
    if job is None:
        logger.warning("scrape job missing %s", job_id)
        return
    if job.status in ("completed", "completed_with_errors", "failed"):
        return

    job.status = "running"
    job.started_at = job.started_at or _now()
    job.error_message = ""
    stats = dict(job.stats if isinstance(job.stats, dict) else _empty_stats())
    for k, v in _empty_stats().items():
        stats.setdefault(k, v)
    db.flush()

    budget = budgets()
    city = job.location.strip()
    hard_errors: list[str] = []
    enrich_failures = 0
    pages_job_budget = budget.max_pages_per_job

    try:
        check_scrape_prerequisites(db)
        queries = build_search_queries(
            keyword=job.query.strip(),
            location=city,
            sources=job.sources or ["google"],
            max_queries=budget.max_queries_per_job,
        )

        seen_candidate_urls: set[str] = set()

        for platform, search_q in queries:
            if job.leads_found >= job.max_results:
                break
            stats["search_queries_run"] += 1
            outcome: FirecrawlSearchOutcome = firecrawl_client.search_web_with_outcome(
                search_q,
                limit=budget.max_results_per_query,
                db=db,
            )
            if not outcome.ok:
                stats["partial"] = True
                msg = outcome.error_message or outcome.error_code
                if msg:
                    stats["firecrawl_errors"].append(msg[:200])
                if outcome.error_code == "FIRECRAWL_NOT_CONFIGURED":
                    raise AppError(outcome.error_code, msg, 503)
                if outcome.error_code == "FIRECRAWL_AUTH":
                    raise AppError(outcome.error_code, msg, 502)
                hard_errors.append(msg)
                continue
            if outcome.empty:
                stats["partial"] = True
                continue

            hits = normalize_firecrawl_hits(outcome.hits, platform=platform)
            stats["search_results"] += len(hits)

            for hit in hits:
                if job.leads_found >= job.max_results:
                    break
                url = hit.url
                compare_key = hit.metadata.get("compare_key") or url
                if compare_key in seen_candidate_urls:
                    continue
                seen_candidate_urls.add(compare_key)
                stats["unique_candidate_urls"] += 1
                stats["candidates_seen"] += 1

                title = hit.title
                snippet = hit.snippet
                pre_candidates = extract_contacts_from_content(snippet, source_url=url)
                official_guess = _extract_official_website_from_text(snippet)

                crawl_snippets = _snippet_list(None, snippet)
                page_candidates, resolved_site = [], official_guess
                if pages_job_budget > 0:
                    crawl_snippets, page_candidates, resolved_site = _crawl_institute_pages(
                        db,
                        discovery_url=url,
                        official_website=official_guess,
                        snippets=list(crawl_snippets),
                        stats=stats,
                        pages_budget=pages_job_budget,
                    )
                    pages_job_budget = max(0, budget.max_pages_per_job - stats["pages_attempted"])

                all_candidates = pre_candidates + page_candidates
                stats["contacts_extracted"] += len(all_candidates)
                stats["contacts_syntax_valid"] += sum(1 for c in all_candidates if c.status == "syntax_valid")

                lead, created, new_content = _upsert_lead(
                    db,
                    job=job,
                    platform=platform,
                    url=url,
                    title=title,
                    snippet=snippet,
                    city=city,
                    official_website=resolved_site,
                )

                for part in crawl_snippets:
                    if lead.profile and _append_raw_snippet(lead.profile, part, limit=8000):
                        new_content = True

                if created:
                    job.leads_found += 1
                    stats["leads_created"] += 1
                elif new_content:
                    stats["leads_updated"] += 1
                    job.leads_updated = int(getattr(job, "leads_updated", 0) or 0) + 1
                else:
                    stats["duplicates_skipped"] += 1
                    logger.info("Skipping duplicate institute %s — no new public data", lead.dedupe_key)
                    continue

                snippets_for_ai = _snippet_list(lead.profile.raw_snippets if lead.profile else None, snippet)
                source_blob = "\n\n".join(snippets_for_ai)

                payload_from_det = apply_evidence_gate(
                    institute_enrich_service._empty_profile(),
                    source_blob=source_blob,
                    deterministic=all_candidates,
                    fallback_name=title or lead.display_name,
                    discovery_url=resolved_site or url,
                )

                try:
                    ai_payload, confidence = institute_enrich_service.enrich_from_snippets(
                        db,
                        title=title or lead.display_name,
                        url=resolved_site or url,
                        snippets=snippets_for_ai,
                    )
                except AppError as exc:
                    if exc.code in ("AI_DISABLED", "AI_ERROR", "AI_AUTH_FAILED", "AI_RATE_LIMIT", "AI_UNSUPPORTED"):
                        enrich_failures += 1
                        logger.warning("Enrich skipped for %s: %s", url, exc.message)
                        ai_payload = payload_from_det
                        confidence = 0.0
                    else:
                        raise
                except Exception as exc:
                    enrich_failures += 1
                    logger.warning("Enrich skipped for %s: %s", url, exc)
                    ai_payload = payload_from_det
                    confidence = 0.0

                gated = apply_evidence_gate(
                    ai_payload,
                    source_blob=source_blob,
                    deterministic=all_candidates,
                    fallback_name=title or lead.display_name,
                    discovery_url=resolved_site or url,
                )

                if lead.profile is None:
                    lead.profile = InstituteLeadProfile(lead_id=lead.id)
                    db.add(lead.profile)
                previous = dict(lead.profile.payload if isinstance(lead.profile.payload, dict) else {})
                merged = merge_lead_payload(previous, gated, source_blob=source_blob)
                if resolved_site and looks_like_official_site(resolved_site):
                    merged["website"] = resolved_site
                    merge_identity_keys_on_official_site(lead, website=resolved_site, name=str(merged.get("name") or title))

                lead.profile.payload = merged
                lead.profile.confidence = max(float(lead.profile.confidence or 0), float(confidence or 0))
                lead.display_name = (merged.get("name") or lead.display_name or title)[:190]
                institute_enrich_service.sync_lead_completeness_score(lead)

                if merged.get("identity_review"):
                    lead.status = "needs_review"
                    stats["profiles_needs_review"] += 1
                elif lead.completeness_score >= 40:
                    if lead.status not in ("enriched", "ready", "sent", "replied", "needs_review"):
                        job.leads_enriched += 1
                        stats["profiles_enriched"] += 1
                    if lead.status in ("discovered", "skipped_incomplete"):
                        lead.status = "enriched"
                db.flush()

        stats["leads_created"] = job.leads_found
        stats["partial"] = bool(stats["partial"] or hard_errors or stats["firecrawl_errors"])

        if hard_errors and job.leads_found == 0 and not stats["search_results"]:
            job.status = "failed"
            job.error_message = hard_errors[0][:2000]
        elif stats["partial"] or hard_errors:
            job.status = "completed_with_errors"
            parts = [e for e in hard_errors if e][:3]
            if enrich_failures and job.leads_enriched == 0 and job.leads_found > 0:
                parts.append(
                    "Leads were discovered but AI enrichment failed partially. Check Platform AI settings."
                )
            elif enrich_failures:
                parts.append(f"{enrich_failures} lead(s) could not be enriched by AI.")
            if stats["firecrawl_errors"]:
                parts.append(f"{len(stats['firecrawl_errors'])} Firecrawl warning(s).")
            job.error_message = " ".join(parts)[:2000]
        else:
            job.status = "completed"
            if enrich_failures and job.leads_enriched == 0 and job.leads_found > 0:
                job.error_message = (
                    "Leads were discovered but AI enrichment failed. Enable Platform AI under Admin → Settings → AI "
                    "(API key + Institute outreach enrichment), then re-run or enrich manually."
                )[:2000]
            elif enrich_failures:
                job.error_message = f"{enrich_failures} lead(s) could not be enriched by AI."[:2000]

        job.stats = stats
        job.finished_at = _now()
    except AppError as exc:
        job.status = "failed"
        job.error_message = exc.message[:2000]
        job.stats = stats
        job.finished_at = _now()
    except Exception as exc:
        logger.exception("scrape job %s failed", job_id)
        job.status = "failed"
        job.error_message = str(exc)[:2000]
        job.stats = stats
        job.finished_at = _now()
