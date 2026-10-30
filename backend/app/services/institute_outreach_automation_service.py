"""Always-on outreach pipeline driven by Celery beat."""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.app.core.config import settings
from backend.app.core.errors import AppError
from backend.app.models.outreach import InstituteLead, InstituteScrapeJob
from backend.app.services import (
    institute_lead_complete_service,
    institute_outreach_service,
    institute_scrape_service,
    platform_settings_service,
)
from backend.app.services.email_service import get_email_sender

logger = logging.getLogger("applyxai.outreach.automation")

_SKIP_STATUSES = frozenset({"sent", "converted", "skipped_incomplete"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _active_scrape_job(db: Session) -> bool:
    return (
        db.scalar(
            select(InstituteScrapeJob.id).where(InstituteScrapeJob.status.in_(("queued", "running"))).limit(1)
        )
        is not None
    )


def _next_keyword_city(campaign: dict) -> tuple[str, str, int]:
    keywords = campaign["keywords"]
    cities = campaign["cities"]
    combos = [(k, c) for k in keywords for c in cities]
    if not combos:
        return "IT training institute", "Bangalore", 0
    idx = int(campaign.get("rotation_index") or 0) % len(combos)
    keyword, city = combos[idx]
    return keyword, city, (idx + 1) % len(combos)


def _try_complete_profile(db: Session) -> str | None:
    lead = db.scalar(
        select(InstituteLead)
        .options(joinedload(InstituteLead.profile))
        .where(
            InstituteLead.completeness_score < 100,
            ~InstituteLead.status.in_(tuple(_SKIP_STATUSES)),
        )
        .order_by(InstituteLead.created_at.asc())
        .limit(1)
    )
    if lead is None:
        return None
    score_before = lead.completeness_score
    try:
        institute_lead_complete_service.complete_lead_profile(db, lead)
    except AppError as exc:
        logger.warning("Complete profile failed for %s: %s", lead.id, exc.message)
        lead.status = "skipped_incomplete"
        return f"complete_failed:{lead.id}"
    except Exception:
        logger.exception("Complete profile error for %s", lead.id)
        lead.status = "skipped_incomplete"
        return f"complete_error:{lead.id}"

    db.refresh(lead)
    if lead.completeness_score < 100:
        lead.status = "skipped_incomplete"
        db.flush()
        return f"skipped_incomplete:{lead.id}"
    db.flush()
    return f"complete:{lead.id}:{score_before}->{lead.completeness_score}"


def _try_generate(db: Session) -> str | None:
    leads = db.scalars(
        select(InstituteLead)
        .options(joinedload(InstituteLead.profile), joinedload(InstituteLead.messages))
        .where(
            InstituteLead.completeness_score >= 100,
            ~InstituteLead.status.in_(tuple(_SKIP_STATUSES)),
        )
        .order_by(InstituteLead.created_at.asc())
        .limit(20)
    ).unique().all()
    for lead in leads:
        if any(m.channel == "email" for m in (lead.messages or [])):
            continue
        try:
            institute_outreach_service.generate_proposal(db, lead)
        except AppError as exc:
            logger.warning("Generate failed for %s: %s", lead.id, exc.message)
            continue
        return f"generate:{lead.id}"
    return None


def _try_send(db: Session) -> str | None:
    campaign = platform_settings_service.get_outreach_campaign(db)
    now = _now()
    next_at = _parse_iso(campaign.get("next_outreach_send_at"))
    if next_at and now < next_at:
        return None

    leads = db.scalars(
        select(InstituteLead)
        .options(joinedload(InstituteLead.profile), joinedload(InstituteLead.messages))
        .where(InstituteLead.completeness_score >= 100, InstituteLead.status != "sent")
        .order_by(InstituteLead.created_at.asc())
        .limit(20)
    ).unique().all()

    mailer = get_email_sender(db)
    for lead in leads:
        if lead.status in _SKIP_STATUSES:
            continue
        email_draft = next((m for m in (lead.messages or []) if m.channel == "email" and m.status == "draft"), None)
        wa_draft = next((m for m in (lead.messages or []) if m.channel == "whatsapp" and m.status == "draft"), None)
        if not email_draft or not wa_draft:
            continue
        profile = lead.profile.payload if lead.profile else {}
        if not (profile.get("emails") and profile.get("phones")):
            continue
        try:
            institute_outreach_service.send_outreach(db, lead, ["email", "whatsapp"], mailer=mailer)
        except AppError as exc:
            logger.warning("Send failed for %s: %s", lead.id, exc.message)
            continue

        min_sec = int(campaign.get("send_interval_min_sec") or 60)
        max_sec = int(campaign.get("send_interval_max_sec") or 120)
        delay = random.randint(min_sec, max_sec)
        updated = dict(campaign)
        updated["last_outreach_send_at"] = now.isoformat()
        updated["next_outreach_send_at"] = (now + timedelta(seconds=delay)).isoformat()
        platform_settings_service.save_outreach_campaign(db, updated)
        return f"send:{lead.id}"
    return None


def _try_scrape(db: Session, campaign: dict) -> str | None:
    if _active_scrape_job(db):
        return None
    if not campaign.get("public_listing_attestation"):
        return None
    try:
        institute_scrape_service.check_scrape_prerequisites(db)
    except AppError as exc:
        logger.debug("Scrape prerequisites: %s", exc.message)
        return None

    keyword, city, next_index = _next_keyword_city(campaign)
    updated = dict(campaign)
    updated["rotation_index"] = next_index
    platform_settings_service.save_outreach_campaign(db, updated)

    job = institute_scrape_service.create_job(
        db,
        admin_user_id=None,
        query=keyword,
        location=city,
        sources=campaign["sources"],
        max_results=campaign["max_results"],
    )
    db.commit()
    institute_outreach_service.dispatch_scrape_job(db, job)
    return f"scrape:{job.id}:{keyword}:{city}"


def run_automation_tick(db: Session) -> str:
    """Run at most one pipeline action per invocation."""
    if not settings.OUTREACH_AUTOMATION_ENABLED:
        return "disabled"

    for step in (_try_complete_profile, _try_generate, _try_send):
        action = step(db)
        if action:
            logger.info("Outreach automation: %s", action)
            return action

    campaign = platform_settings_service.get_outreach_campaign(db)
    action = _try_scrape(db, campaign)
    if action:
        logger.info("Outreach automation: %s", action)
        return action

    return "idle"
