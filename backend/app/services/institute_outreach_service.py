"""Institute lead listing, proposals, send, and convert — admin outreach."""

from __future__ import annotations

import logging
import re
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.app.core.config import settings
from backend.app.core.errors import AppError
from backend.app.core.pagination import PageParams, page_response, paginate
from backend.app.models.enums import InstituteStatus
from backend.app.models.outreach import (
    InstituteLead, InstituteLeadProfile, InstituteOutreachMessage, InstituteScrapeJob, WhatsAppSession,
)
from backend.app.models.user import User
from backend.app.services import (
    institute_enrich_service,
    institute_lead_complete_service,
    institute_outreach_chat_service,
    institute_outreach_bot_service,
    institute_proposal_service,
    institute_scrape_service,
    whatsapp_bridge_client,
)
from backend.app.services.auth_service import normalize_email
from backend.app.services.email_service import Email, password_reset_email
from backend.app.services.institute_service import register as register_institute
from backend.app.core.security import hash_password
from backend.app.services import auth_service

logger = logging.getLogger("applyxai.outreach")

_MAX_BULK_ACTION_LEADS = 25
_PROFILE_COMPLETION_TERMINAL_STATUSES = frozenset({"sent", "converted", "skipped_incomplete"})
_EMAIL_IN_TEXT = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def job_out(job: InstituteScrapeJob) -> dict:
    stats = job.stats if isinstance(job.stats, dict) else {}
    return {
        "id": str(job.id),
        "query": job.query,
        "location": job.location,
        "sources": job.sources or [],
        "max_results": job.max_results,
        "status": job.status,
        "leads_found": job.leads_found,
        "leads_updated": int(getattr(job, "leads_updated", 0) or 0),
        "leads_enriched": job.leads_enriched,
        "stats": stats,
        "error_message": job.error_message,
        "started_at": _iso(job.started_at),
        "finished_at": _iso(job.finished_at),
        "created_at": _iso(job.created_at),
    }


def list_jobs(db: Session, params: PageParams, *, owner_institute_id=None) -> dict:
    stmt = select(InstituteScrapeJob).order_by(InstituteScrapeJob.created_at.desc())
    if owner_institute_id is not None:
        stmt = stmt.where(InstituteScrapeJob.owner_institute_id == owner_institute_id)
    items, total = paginate(db, stmt, params)
    return page_response([job_out(j) for j in items], total, params)


def get_job(db: Session, job_id: uuid.UUID) -> InstituteScrapeJob:
    job = db.get(InstituteScrapeJob, job_id)
    if job is None:
        raise AppError("NOT_FOUND", "Scrape job not found.", 404)
    return job


def lead_out(lead: InstituteLead) -> dict:
    raw_profile = lead.profile.payload if lead.profile else None
    profile = raw_profile if isinstance(raw_profile, dict) else {}
    messages = [
        {
            "id": str(m.id),
            "channel": m.channel,
            "subject": m.subject,
            "body": m.body,
            "status": m.status,
            "sent_at": _iso(m.sent_at),
        }
        for m in (lead.messages or [])
    ]
    return {
        "id": str(lead.id),
        "job_id": str(lead.job_id) if lead.job_id else None,
        "source_platform": lead.source_platform,
        "source_url": lead.source_url,
        "display_name": lead.display_name,
        "status": lead.status,
        "completeness_score": lead.completeness_score,
        "profile_completing": lead.status == "completing_profile",
        "institute_id": str(lead.institute_id) if lead.institute_id else None,
        "profile": profile,
        "confidence": lead.profile.confidence if lead.profile else 0,
        "messages": messages,
        "whatsapp_phone": lead.whatsapp_phone or "",
        "created_at": _iso(lead.created_at),
    }


def lead_dashboard_stats(db: Session) -> dict:
    stale_zero = db.scalars(
        select(InstituteLead)
        .options(selectinload(InstituteLead.profile))
        .where(InstituteLead.completeness_score == 0)
        .limit(500)
    ).all()
    if institute_enrich_service.sync_leads_completeness_scores(stale_zero):
        db.flush()

    total = int(db.scalar(select(func.count()).select_from(InstituteLead)) or 0)
    completing = int(
        db.scalar(
            select(func.count()).select_from(InstituteLead).where(InstituteLead.status == "completing_profile")
        )
        or 0
    )
    full_profile = int(
        db.scalar(select(func.count()).select_from(InstituteLead).where(InstituteLead.completeness_score >= 100))
        or 0
    )
    rows = db.execute(select(InstituteLead.status, func.count()).group_by(InstituteLead.status)).all()
    by_status = {str(status): int(count) for status, count in rows}
    sent = by_status.get("sent", 0) + by_status.get("replied", 0)
    enriched = by_status.get("enriched", 0)
    discovered = by_status.get("discovered", 0)
    skipped = by_status.get("skipped_incomplete", 0)
    return {
        "total": total,
        "profile_completing": completing,
        "profile_completion_pending": completing,
        "completeness_full": full_profile,
        "enriched": enriched,
        "discovered": discovered,
        "sent": sent,
        "skipped_incomplete": skipped,
        "by_status": by_status,
    }


def list_leads(
    db: Session,
    params: PageParams,
    *,
    job_id: uuid.UUID | None = None,
    status: str | None = None,
    source: str | None = None,
    profile_complete: bool | None = None,
    q: str | None = None,
    owner_institute_id=None,
) -> dict:
    stmt = select(InstituteLead).options(
        selectinload(InstituteLead.profile),
        selectinload(InstituteLead.messages),
    )
    if owner_institute_id is not None:
        stmt = stmt.where(InstituteLead.owner_institute_id == owner_institute_id)
    if job_id:
        stmt = stmt.where(InstituteLead.job_id == job_id)
    if status:
        stmt = stmt.where(InstituteLead.status == status)
    if source:
        stmt = stmt.where(InstituteLead.source_platform == source.strip().lower())
    if profile_complete is True:
        stmt = stmt.where(InstituteLead.completeness_score >= 100)
    elif profile_complete is False:
        stmt = stmt.where(InstituteLead.completeness_score < 100)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                InstituteLead.display_name.ilike(like),
                InstituteLead.source_url.ilike(like),
                InstituteLead.whatsapp_phone.ilike(like),
            )
        )
    stmt = stmt.order_by(InstituteLead.created_at.desc())
    items, total = paginate(db, stmt, params)
    if institute_enrich_service.sync_leads_completeness_scores(items):
        db.flush()
    return page_response([lead_out(lead) for lead in items], total, params)


def recent_whatsapp_sends(db: Session, *, limit: int = 15) -> list[dict]:
    rows = db.scalars(
        select(InstituteOutreachMessage)
        .options(joinedload(InstituteOutreachMessage.lead))
        .where(
            InstituteOutreachMessage.channel == "whatsapp",
            InstituteOutreachMessage.status == "sent",
        )
        .order_by(InstituteOutreachMessage.sent_at.desc())
        .limit(max(1, min(limit, 50)))
    ).all()
    out: list[dict] = []
    for row in rows:
        lead = row.lead
        out.append(
            {
                "lead_id": str(row.lead_id),
                "name": (lead.display_name if lead else "") or "Lead",
                "sent_at": _iso(row.sent_at),
                "preview": (row.body or "")[:120],
            }
        )
    return out


def get_lead(db: Session, lead_id: uuid.UUID) -> InstituteLead:
    lead = db.scalar(
        select(InstituteLead)
        .options(
            joinedload(InstituteLead.profile),
            joinedload(InstituteLead.messages),
            joinedload(InstituteLead.chat_messages),
        )
        .where(InstituteLead.id == lead_id)
    )
    if lead is None:
        raise AppError("NOT_FOUND", "Lead not found.", 404)
    if institute_enrich_service.sync_lead_completeness_score(lead):
        db.flush()
    return lead


def _digits_phone(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _looks_like_phone(token: str) -> bool:
    digits = _digits_phone(token)
    return len(digits) >= 10


def _extract_email(token: str) -> str | None:
    token = token.strip()
    if "@" in token and " " not in token:
        try:
            return normalize_email(token)
        except Exception:
            return None
    match = _EMAIL_IN_TEXT.search(token)
    if match:
        try:
            return normalize_email(match.group(0))
        except Exception:
            return None
    return None


def parse_manual_contact_line(line: str) -> tuple[str | None, str | None, str | None] | None:
    """Parse one line into optional institute name, email, and phone."""
    raw = (line or "").strip()
    if not raw or raw.startswith("#"):
        return None
    parts = [p.strip() for p in re.split(r"[\|,;\t]+", raw) if p.strip()]
    if not parts:
        return None

    email: str | None = None
    phone: str | None = None
    name_parts: list[str] = []

    for part in parts:
        em = _extract_email(part)
        if em:
            email = em
            continue
        if _looks_like_phone(part):
            from backend.app.services.institute_outreach_chat_service import normalize_wa_phone

            phone = normalize_wa_phone(part) or part.strip()
            continue
        name_parts.append(part)

    if len(parts) == 1 and not email and not phone:
        sole = parts[0]
        em = _extract_email(sole)
        if em:
            email = em
        elif _looks_like_phone(sole):
            from backend.app.services.institute_outreach_chat_service import normalize_wa_phone

            phone = normalize_wa_phone(sole) or sole
        else:
            return None

    if not email and not phone:
        return None

    name = " ".join(name_parts).strip() or None
    return name, email, phone


def _default_display_name(*, name: str | None, email: str | None, phone: str | None) -> str:
    if name:
        return name[:190]
    if email:
        domain = email.split("@", 1)[-1]
        label = domain.split(".")[0].replace("-", " ").title()
        return (label or domain)[:190]
    if phone:
        digits = _digits_phone(phone)
        return f"Lead …{digits[-4:]}" if len(digits) >= 4 else "Lead"
    return "Institute lead"


def upsert_manual_lead(
    db: Session,
    *,
    name: str | None,
    email: str | None,
    phone: str | None,
) -> tuple[InstituteLead, bool]:
    """Create or update a manually imported lead keyed by email or phone."""
    emails: list[str] = []
    phones: list[str] = []
    dedupe = ""

    if email:
        emails = [email]
        dedupe = f"manual:email:{email}"
    if phone:
        norm = phone.strip()
        digits = _digits_phone(norm)
        if len(digits) >= 10:
            phones = [norm]
            if not dedupe:
                dedupe = f"manual:phone:{digits}"

    if not dedupe:
        raise AppError("VALIDATION_ERROR", "Each line must include a valid email or phone number.", 422)

    display = _default_display_name(name=name, email=email, phone=phone)
    existing = db.scalar(
        select(InstituteLead)
        .options(joinedload(InstituteLead.profile))
        .where(InstituteLead.dedupe_key == dedupe)
    )
    if existing is not None:
        payload = dict(existing.profile.payload if existing.profile and isinstance(existing.profile.payload, dict) else {})
        merged_emails = list(payload.get("emails") or [])
        for em in emails:
            if em not in merged_emails:
                merged_emails.append(em)
        payload["emails"] = merged_emails[:5]
        merged_phones = list(payload.get("phones") or [])
        for ph in phones:
            if ph not in merged_phones:
                merged_phones.append(ph)
        payload["phones"] = merged_phones[:5]
        if name:
            payload["name"] = name[:190]
            existing.display_name = name[:190]
        elif not payload.get("name"):
            payload["name"] = display
        if phones and not existing.whatsapp_phone:
            existing.whatsapp_phone = phones[0][:32]
        if existing.profile is None:
            existing.profile = InstituteLeadProfile(lead_id=existing.id, payload=payload)
            db.add(existing.profile)
        else:
            existing.profile.payload = payload
        institute_enrich_service.sync_lead_completeness_score(existing)
        db.flush()
        return existing, False

    lead = InstituteLead(
        job_id=None,
        source_platform="manual",
        source_url="",
        dedupe_key=dedupe,
        display_name=display,
        status="discovered",
    )
    if phones:
        lead.whatsapp_phone = phones[0][:32]
    db.add(lead)
    db.flush()
    payload = {
        "name": display,
        "institute_type": "OTHER",
        "contact_name": "",
        "emails": emails,
        "phones": phones,
        "website": "",
        "description": "",
        "programs": [],
        "address": {"line": "", "city": "", "state": "", "pin": "", "country": "India"},
        "social": {},
    }
    profile = InstituteLeadProfile(lead_id=lead.id, payload=payload)
    db.add(profile)
    db.flush()
    institute_enrich_service.sync_lead_completeness_score(lead)
    return lead, True


def bulk_import_leads(db: Session, contacts_text: str, *, enrich: bool = True) -> dict:
    lines = [ln.strip() for ln in contacts_text.replace("\r", "").split("\n") if ln.strip()]
    if not lines:
        raise AppError("VALIDATION_ERROR", "Add at least one email or phone number (one per line).", 422)

    items: list[dict] = []
    created = skipped = invalid = 0
    enrich_lead_ids: list[uuid.UUID] = []

    for line in lines:
        parsed = parse_manual_contact_line(line)
        if parsed is None:
            invalid += 1
            items.append({"line": line, "status": "invalid", "error": "Could not parse email or phone on this line."})
            continue
        name, email, phone = parsed
        try:
            lead, was_new = upsert_manual_lead(db, name=name, email=email, phone=phone)
        except AppError as exc:
            invalid += 1
            items.append({"line": line, "status": "invalid", "error": exc.message})
            continue

        if was_new:
            created += 1
            row_status = "created"
        else:
            skipped += 1
            row_status = "existing"

        entry: dict = {
            "line": line,
            "status": row_status,
            "lead_id": str(lead.id),
            "display_name": lead.display_name,
            "completeness_score": lead.completeness_score,
        }

        if enrich:
            enrich_lead_ids.append(lead.id)
            entry["enrich_queued"] = True

        items.append(entry)

    return {
        "created": created,
        "existing": skipped,
        "invalid": invalid,
        "enrich_queued": len(enrich_lead_ids),
        "items": items,
        "_enrich_lead_ids": enrich_lead_ids,
    }


def mark_leads_completing_profile(db: Session, lead_ids: list[uuid.UUID]) -> None:
    for lid in lead_ids:
        lead = db.get(InstituteLead, lid)
        if lead and lead.status not in _PROFILE_COMPLETION_TERMINAL_STATUSES:
            lead.status = "completing_profile"
    db.flush()


def _clear_completing_profile_status(lead_id: uuid.UUID) -> None:
    from backend.app.core.database import SessionLocal

    with SessionLocal() as db:
        lead = db.get(InstituteLead, lead_id)
        if lead and lead.status == "completing_profile":
            lead.status = "discovered"
            db.commit()


def run_background_complete_lead_profile(lead_id: uuid.UUID) -> None:
    from backend.app.core.database import SessionLocal

    with SessionLocal() as db:
        try:
            lead = get_lead(db, lead_id)
            institute_lead_complete_service.complete_lead_profile(db, lead)
            db.commit()
        except Exception:
            db.rollback()
            _clear_completing_profile_status(lead_id)
            logger.exception("Background complete profile failed for lead %s", lead_id)
            raise


def dispatch_bulk_lead_enrichment(lead_ids: list[uuid.UUID]) -> None:
    """Queue complete-profile runs after bulk import (Celery, or daemon thread if Celery is down)."""
    if not lead_ids:
        return
    from backend.app.core.database import SessionLocal

    with SessionLocal() as db:
        mark_leads_completing_profile(db, lead_ids)
        db.commit()

    id_strs = [str(i) for i in lead_ids]
    try:
        from backend.app.worker import run_bulk_lead_import_enrichment

        run_bulk_lead_import_enrichment.delay(id_strs)
        return
    except Exception:
        logger.info("Celery unavailable; running bulk enrichment for %s leads in background thread", len(id_strs))

    import threading

    def _run() -> None:
        for lid in lead_ids:
            run_background_complete_lead_profile(lid)

    threading.Thread(target=_run, name="bulk-lead-enrichment", daemon=True).start()


def enhance_lead_profile(db: Session, lead: InstituteLead) -> dict:
    """Re-run AI enrichment on saved snippets and profile text (no new Firecrawl search)."""
    from backend.app.services.platform_settings_service import get_effective_ai

    ai = get_effective_ai(db)
    if not ai.feature_on("outreach"):
        raise AppError(
            "AI_DISABLED",
            "Enable Platform AI under Admin → Settings → AI with Institute outreach enrichment.",
            503,
        )

    if lead.profile is None:
        lead.profile = InstituteLeadProfile(lead_id=lead.id, payload={})
        db.add(lead.profile)
        db.flush()

    existing = dict(lead.profile.payload if isinstance(lead.profile.payload, dict) else {})
    snippets = [str(s).strip() for s in (lead.profile.raw_snippets or []) if str(s).strip()]
    if not snippets:
        parts = [
            str(existing.get("name") or lead.display_name or ""),
            str(existing.get("description") or ""),
            str(existing.get("website") or lead.source_url or ""),
        ]
        for key in ("emails", "phones", "programs"):
            raw = existing.get(key)
            if isinstance(raw, list):
                parts.extend(str(x) for x in raw if str(x).strip())
        blob = "\n".join(p for p in parts if p.strip())
        if blob.strip():
            snippets = [blob[:8000]]

    if not snippets:
        raise AppError(
            "NOT_READY",
            "Nothing to enhance yet. Run Complete profile or add institute name, email, or phone.",
            422,
        )

    score_before = lead.completeness_score
    title = (existing.get("name") or lead.display_name or "Institute").strip()
    url = str(existing.get("website") or lead.source_url or "").strip()

    new_payload, confidence = institute_enrich_service.enrich_from_snippets(
        db,
        title=title,
        url=url,
        snippets=snippets[-20:],
        complete=False,
    )
    merged = institute_enrich_service.merge_profiles(existing, new_payload)
    for em in existing.get("emails") or []:
        if em and em not in merged.get("emails", []):
            merged.setdefault("emails", []).append(em)
    merged["emails"] = (merged.get("emails") or [])[:5]
    for ph in existing.get("phones") or []:
        if ph and ph not in merged.get("phones", []):
            merged.setdefault("phones", []).append(ph)
    merged["phones"] = (merged.get("phones") or [])[:5]

    lead.profile.payload = merged
    lead.profile.confidence = confidence
    lead.display_name = (merged.get("name") or lead.display_name or title)[:190]
    institute_enrich_service.sync_lead_completeness_score(lead)
    if lead.completeness_score >= 40 and lead.status in ("discovered", "skipped_incomplete"):
        lead.status = "enriched"
    db.flush()
    return {"lead": lead, "score_before": score_before, "score_after": lead.completeness_score}


def bulk_leads_action(db: Session, lead_ids: list[uuid.UUID], action: str) -> dict:
    if action not in ("complete", "enhance"):
        raise AppError("VALIDATION_ERROR", "action must be complete or enhance.", 422)
    if len(lead_ids) > _MAX_BULK_ACTION_LEADS:
        raise AppError(
            "VALIDATION_ERROR",
            f"Select at most {_MAX_BULK_ACTION_LEADS} leads per bulk action.",
            422,
        )

    if action == "complete":
        institute_scrape_service.check_scrape_prerequisites(db)

    items: list[dict] = []
    succeeded = failed = 0

    for lid in lead_ids:
        try:
            lead = get_lead(db, lid)
        except AppError as exc:
            failed += 1
            items.append({"lead_id": str(lid), "ok": False, "error": exc.message})
            continue

        try:
            if action == "complete":
                result = institute_lead_complete_service.complete_lead_profile(db, lead)
                items.append(
                    {
                        "lead_id": str(lid),
                        "ok": True,
                        "display_name": lead.display_name,
                        "completeness_score": lead.completeness_score,
                        "completion": result.get("completion"),
                    }
                )
            else:
                result = enhance_lead_profile(db, lead)
                items.append(
                    {
                        "lead_id": str(lid),
                        "ok": True,
                        "display_name": lead.display_name,
                        "completeness_score": lead.completeness_score,
                        "score_before": result["score_before"],
                        "score_after": result["score_after"],
                    }
                )
            succeeded += 1
        except AppError as exc:
            failed += 1
            items.append(
                {
                    "lead_id": str(lid),
                    "ok": False,
                    "display_name": lead.display_name,
                    "error": exc.message,
                }
            )
        except Exception as exc:
            failed += 1
            logger.exception("Bulk %s failed for lead %s", action, lid)
            items.append(
                {
                    "lead_id": str(lid),
                    "ok": False,
                    "display_name": lead.display_name,
                    "error": str(exc)[:500],
                }
            )

    return {"action": action, "succeeded": succeeded, "failed": failed, "items": items}


def update_lead_profile(db: Session, lead: InstituteLead, payload: dict) -> InstituteLead:
    if lead.profile is None:
        lead.profile = InstituteLeadProfile(lead_id=lead.id, payload=payload)
        db.add(lead.profile)
    else:
        lead.profile.payload = payload
    institute_enrich_service.sync_lead_completeness_score(lead)
    lead.display_name = (payload.get("name") or lead.display_name)[:190]
    if lead.completeness_score >= 40:
        lead.status = "ready"
    db.flush()
    return lead


def generate_proposal(db: Session, lead: InstituteLead) -> InstituteLead:
    if lead.profile is None or not lead.profile.payload:
        raise AppError("NOT_READY", "Enrich the lead profile before generating a proposal.", 422)
    if lead.completeness_score < 100:
        raise AppError(
            "PROFILE_INCOMPLETE",
            "Complete the lead profile to 100% before generating a proposal.",
            422,
        )
    subject, body, html, wa = institute_proposal_service.generate_proposals(db, lead.profile.payload)
    _upsert_message(db, lead, "email", subject, body, html)
    _upsert_message(db, lead, "whatsapp", "", wa, "")
    lead.status = "proposal_ready"
    db.flush()
    return lead


def _upsert_message(db: Session, lead: InstituteLead, channel: str, subject: str, body: str, html: str) -> None:
    existing = next((m for m in lead.messages if m.channel == channel and m.status == "draft"), None)
    if existing is None:
        existing = InstituteOutreachMessage(lead_id=lead.id, channel=channel, status="draft")
        db.add(existing)
        lead.messages.append(existing)
    existing.subject = subject[:500]
    existing.body = body
    existing.html = html


def send_outreach(db: Session, lead: InstituteLead, channels: list[str], *, mailer) -> dict:
    if lead.completeness_score < 100:
        raise AppError(
            "PROFILE_INCOMPLETE",
            "Lead profile must be 100% complete before sending outreach.",
            422,
        )
    if not lead.messages:
        raise AppError("NOT_READY", "Generate a proposal first.", 422)
    sent: dict[str, str] = {}
    profile = lead.profile.payload if lead.profile else {}

    if "email" in channels and "whatsapp" in channels:
        emails = profile.get("emails") or []
        phones = profile.get("phones") or []
        if not emails or not phones:
            raise AppError(
                "NO_CONTACT",
                "Lead needs both email and phone to send email and WhatsApp.",
                422,
            )

    if "email" in channels:
        msg = next((m for m in lead.messages if m.channel == "email" and m.status == "draft"), None)
        if msg is None:
            raise AppError("NOT_READY", "Email draft missing.", 422)
        emails = profile.get("emails") or []
        if not emails:
            raise AppError("NO_EMAIL", "Lead has no email address.", 422)
        to = emails[0]
        mailer.send(Email(to=to, subject=msg.subject, body=msg.body, html=msg.html or ""))
        msg.status = "sent"
        msg.sent_at = _now()
        sent["email"] = to

    if "whatsapp" in channels:
        msg = next((m for m in lead.messages if m.channel == "whatsapp" and m.status == "draft"), None)
        if msg is None:
            raise AppError("NOT_READY", "WhatsApp draft missing.", 422)
        phones = profile.get("phones") or []
        if not phones:
            raise AppError("NO_PHONE", "Lead has no phone number.", 422)
        wa_phone = institute_outreach_chat_service.normalize_wa_phone(str(phones[0]))
        lead.whatsapp_phone = wa_phone[:32]
        image_path = institute_proposal_service.proposal_image_file_path()
        media = str(image_path) if image_path.is_file() else None
        result = whatsapp_bridge_client.send_message(
            wa_phone or str(phones[0]),
            msg.body,
            media_path=media,
            caption=msg.body,
        )
        msg.status = "sent"
        msg.sent_at = _now()
        msg.provider_response = str(result)[:2000]
        institute_outreach_chat_service.record_outbound(db, lead, body=msg.body)
        institute_outreach_bot_service.enable_outreach_chatbot(db, lead)
        sent["whatsapp"] = wa_phone or str(phones[0])

    lead.status = "sent"
    db.flush()
    return sent


def convert_to_institute(db: Session, lead: InstituteLead, *, mailer) -> dict:
    if lead.institute_id:
        raise AppError("ALREADY_CONVERTED", "Lead is already linked to an institute.", 409)
    profile = lead.profile.payload if lead.profile else {}
    emails = profile.get("emails") or []
    if not emails:
        raise AppError("NO_EMAIL", "Lead needs an email to create an institute login.", 422)
    email = normalize_email(emails[0])
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise AppError("EMAIL_TAKEN", "That email already has an account.", 409)

    temp_password = secrets.token_urlsafe(16)
    user = User(
        email=email,
        password_hash=hash_password(temp_password),
        first_name=(profile.get("contact_name") or profile.get("name") or "Institute")[:100],
        last_name="",
        is_verified=True,
    )
    db.add(user)
    db.flush()

    institute = register_institute(
        db,
        user,
        name=(profile.get("name") or lead.display_name or "Institute")[:190],
        contact_name=(profile.get("contact_name") or "")[:190],
        phone=(profile.get("phones") or [""])[0][:32] if profile.get("phones") else "",
        institute_type=(profile.get("institute_type") or "OTHER")[:32],
        source="admin",
        status=InstituteStatus.PENDING,
    )
    lead.institute_id = institute.id
    lead.status = "converted"
    db.flush()

    db.commit()
    _user, token = auth_service.new_password_reset_token(db, email)
    if token:
        mail = password_reset_email(email, token, db)
        mailer.send(mail)
    return {"institute_id": str(institute.id), "email": email}


def send_whatsapp_test(phone: str, text: str, db: Session | None = None) -> dict:
    from backend.app.services import whatsapp_cloud_client
    from backend.app.services.platform_settings_service import get_outreach_admin
    provider = "bridge"
    if db is not None:
        provider = str(get_outreach_admin(db).get("whatsapp_provider") or "bridge")
    if provider == "cloud":
        return whatsapp_cloud_client.send_text(phone, text)
    remote = whatsapp_bridge_client.get_status()
    if remote.get("status") != "connected" or not remote.get("ready"):
        raise AppError(
            "WHATSAPP_NOT_READY",
            "WhatsApp is not connected. Scan the QR code on Admin → Outreach → WhatsApp.",
            503,
        )
    return whatsapp_bridge_client.send_message(phone.strip(), text.strip())


def sync_whatsapp_session(db: Session) -> dict:
    from backend.app.core.config import settings

    remote = whatsapp_bridge_client.get_status()
    row = db.scalar(select(WhatsAppSession).where(WhatsAppSession.session_key == "default"))
    if row is None:
        row = WhatsAppSession(session_key="default")
        db.add(row)
    row.status = remote.get("status") or "disconnected"
    if row.status == "connected" and not row.connected_at:
        row.connected_at = _now()
    row.last_error = str(remote.get("error") or "")[:2000]
    db.flush()
    api_secret = bool((settings.WHATSAPP_BRIDGE_SECRET or "").strip())
    bridge_inbound = bool(remote.get("inbound_enabled"))
    return {
        **remote,
        "session_id": str(row.id),
        "connected_at": _iso(row.connected_at),
        "bridge_url": (settings.WHATSAPP_BRIDGE_URL or "").rstrip("/") or "http://127.0.0.1:39219",
        "inbound_enabled": api_secret and bridge_inbound,
        "api_inbound_configured": api_secret,
        "bridge_inbound_configured": bridge_inbound,
    }


def dispatch_scrape_job(db: Session, job: InstituteScrapeJob) -> InstituteScrapeJob:
    institute_scrape_service.recover_stale_scrape_jobs(db)
    db.commit()
    try:
        from backend.app.worker import run_institute_scrape_job

        run_institute_scrape_job.delay(str(job.id))
    except Exception:
        logger.info("Celery unavailable; running scrape job %s inline", job.id)
        institute_scrape_service.run_scrape_job(db, job.id)
        db.commit()
        db.refresh(job)
    return job

