"""Institute-scoped outreach: scrape, leads, and WhatsApp chat for campus operators."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import require_institute_member
from backend.app.core.database import get_db
from backend.app.core.errors import AppError, ok
from backend.app.core.pagination import PageParams, page_params
from backend.app.core.rate_limit import get_rate_limiter
from backend.app.schemas.outreach import LeadChatIn, ScrapeJobCreateIn
from backend.app.services import (
    institute_outreach_chat_service,
    institute_outreach_service,
    institute_scrape_service,
)

router = APIRouter(prefix="/institute/outreach", tags=["institute"])


def _owned_job(db: Session, institute_id, job_id: uuid.UUID):
    job = institute_outreach_service.get_job(db, job_id)
    if job.owner_institute_id != institute_id:
        raise AppError("NOT_FOUND", "Scrape job not found.", 404)
    return job


def _owned_lead(db: Session, institute_id, lead_id: uuid.UUID):
    lead = institute_outreach_service.get_lead(db, lead_id)
    if lead.owner_institute_id != institute_id:
        raise AppError("NOT_FOUND", "Lead not found.", 404)
    return lead


@router.post("/scrape-jobs")
def start_scrape_job(
    body: ScrapeJobCreateIn,
    ctx=Depends(require_institute_member),
    db: Session = Depends(get_db),
    limiter=Depends(get_rate_limiter),
):
    user, institute, _member = ctx
    if not body.public_listing_attestation:
        raise AppError("ATTESTATION_REQUIRED", "Confirm leads are from public business listings.", 422)
    limiter.hit("10/hour", "institute-outreach-scrape", str(user.id))
    institute_scrape_service.check_scrape_prerequisites(db)
    job = institute_scrape_service.create_job(
        db,
        admin_user_id=user.id,
        query=body.query,
        location=body.location,
        sources=body.sources,
        max_results=body.max_results,
        owner_institute_id=institute.id,
    )
    db.commit()
    institute_outreach_service.dispatch_scrape_job(db, job)
    return ok(institute_outreach_service.job_out(job))


@router.get("/scrape-jobs")
def list_scrape_jobs(params: PageParams = Depends(page_params), ctx=Depends(require_institute_member),
                     db: Session = Depends(get_db)):
    _user, institute, _member = ctx
    return ok(institute_outreach_service.list_jobs(db, params, owner_institute_id=institute.id))


@router.get("/scrape-jobs/{job_id}")
def scrape_job_detail(job_id: uuid.UUID, ctx=Depends(require_institute_member), db: Session = Depends(get_db)):
    _user, institute, _member = ctx
    job = _owned_job(db, institute.id, job_id)
    return ok(institute_outreach_service.job_out(job))


@router.get("/leads")
def list_leads(
    params: PageParams = Depends(page_params),
    job_id: uuid.UUID | None = None,
    status: str | None = None,
    q: str | None = Query(None, max_length=200),
    ctx=Depends(require_institute_member),
    db: Session = Depends(get_db),
):
    _user, institute, _member = ctx
    return ok(institute_outreach_service.list_leads(
        db, params, job_id=job_id, status=status, q=q, owner_institute_id=institute.id,
    ))


@router.get("/leads/{lead_id}")
def lead_detail(lead_id: uuid.UUID, ctx=Depends(require_institute_member), db: Session = Depends(get_db)):
    _user, institute, _member = ctx
    lead = _owned_lead(db, institute.id, lead_id)
    return ok(institute_outreach_service.lead_out(lead))


@router.get("/leads/{lead_id}/chat")
def lead_chat(lead_id: uuid.UUID, ctx=Depends(require_institute_member), db: Session = Depends(get_db)):
    _user, institute, _member = ctx
    lead = _owned_lead(db, institute.id, lead_id)
    items = institute_outreach_chat_service.list_chat(db, lead, sync_bridge=False)
    db.commit()
    return ok({"items": items, "whatsapp_phone": lead.whatsapp_phone or ""})


@router.post("/leads/{lead_id}/chat")
def lead_chat_send(
    lead_id: uuid.UUID,
    body: LeadChatIn,
    ctx=Depends(require_institute_member),
    db: Session = Depends(get_db),
    limiter=Depends(get_rate_limiter),
):
    user, institute, _member = ctx
    limiter.hit("60/hour", "institute-outreach-chat", str(user.id))
    lead = _owned_lead(db, institute.id, lead_id)
    if body.channel != "whatsapp":
        raise AppError("NOT_SUPPORTED", "Only WhatsApp chat is supported today.", 422)
    result = institute_outreach_chat_service.send_whatsapp_reply(db, lead, body.text)
    db.commit()
    return ok(result)
