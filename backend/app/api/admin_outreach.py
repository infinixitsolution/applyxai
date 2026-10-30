"""Admin institute scraping and outbound marketing."""

import uuid

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from backend.app.api.deps import get_mailer, require_admin
from backend.app.core.rate_limit import RateLimiter, get_rate_limiter
from backend.app.core.database import get_db
from backend.app.core.errors import AppError, ok
from backend.app.core.pagination import PageParams, page_params
from backend.app.models.user import User
from backend.app.schemas.outreach import (
    LeadBulkActionIn,
    LeadBulkImportIn,
    LeadChatIn,
    LeadProfileIn,
    LeadSendIn,
    ScrapeJobCreateIn,
    WhatsappTestSendIn,
)
from backend.app.services import (
    admin_service,
    institute_lead_complete_service,
    institute_outreach_attachment_service,
    institute_outreach_chat_service,
    institute_proposal_image_service,
    institute_outreach_service,
    institute_scrape_service,
)
from backend.app.services.email_service import EmailSender

router = APIRouter(prefix="/admin/outreach", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("/scrape-jobs")
def start_scrape_job(
    body: ScrapeJobCreateIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limiter=Depends(get_rate_limiter),
):
    if not body.public_listing_attestation:
        raise AppError("ATTESTATION_REQUIRED", "Confirm leads are from public business listings.", 422)
    limiter.hit("10/hour", "admin-outreach-scrape", str(admin.id))
    institute_scrape_service.check_scrape_prerequisites(db)
    job = institute_scrape_service.create_job(
        db,
        admin_user_id=admin.id,
        query=body.query,
        location=body.location,
        sources=body.sources,
        max_results=body.max_results,
    )
    admin_service._audit(db, admin, "outreach.scrape.start", None, query=body.query)
    db.commit()
    institute_outreach_service.dispatch_scrape_job(db, job)
    return ok(institute_outreach_service.job_out(job))


@router.get("/scrape-jobs")
def list_scrape_jobs(params: PageParams = Depends(page_params), db: Session = Depends(get_db)):
    return ok(institute_outreach_service.list_jobs(db, params))


@router.get("/scrape-jobs/{job_id}")
def scrape_job_detail(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = institute_outreach_service.get_job(db, job_id)
    return ok(institute_outreach_service.job_out(job))


@router.post("/leads/bulk-import", summary="Import leads by email or phone; optional profile completion")
def bulk_import_leads(
    body: LeadBulkImportIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limiter=Depends(get_rate_limiter),
):
    limiter.hit("20/hour", "admin-outreach-bulk-import", str(admin.id))
    if body.enrich:
        institute_scrape_service.check_scrape_prerequisites(db)
    result = institute_outreach_service.bulk_import_leads(db, body.contacts, enrich=body.enrich)
    enrich_ids = result.pop("_enrich_lead_ids", [])
    admin_service._audit(
        db,
        admin,
        "outreach.leads.bulk_import",
        None,
        created=result.get("created"),
        enrich_queued=result.get("enrich_queued"),
    )
    db.commit()
    if enrich_ids:
        institute_outreach_service.dispatch_bulk_lead_enrichment(enrich_ids)
    return ok(result)


@router.post("/leads/bulk-action", summary="Complete profile or AI-enhance multiple leads")
def bulk_leads_action(
    body: LeadBulkActionIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limiter=Depends(get_rate_limiter),
):
    limiter.hit("30/hour", "admin-outreach-bulk-action", str(admin.id))
    result = institute_outreach_service.bulk_leads_action(db, body.lead_ids, body.action)
    admin_service._audit(
        db,
        admin,
        f"outreach.leads.bulk_{body.action}",
        None,
        succeeded=result.get("succeeded"),
        failed=result.get("failed"),
    )
    db.commit()
    return ok(result)


@router.get("/leads/stats", summary="Outreach leads dashboard counts")
def outreach_leads_stats(db: Session = Depends(get_db)):
    return ok(institute_outreach_service.lead_dashboard_stats(db))


@router.get("/leads")
def list_leads(
    params: PageParams = Depends(page_params),
    job_id: uuid.UUID | None = None,
    status: str | None = None,
    source: str | None = Query(None, max_length=32),
    profile_complete: bool | None = None,
    q: str | None = Query(None, max_length=200),
    db: Session = Depends(get_db),
):
    return ok(
        institute_outreach_service.list_leads(
            db,
            params,
            job_id=job_id,
            status=status,
            source=source,
            profile_complete=profile_complete,
            q=q,
        )
    )


@router.get("/leads/{lead_id}")
def lead_detail(lead_id: uuid.UUID, db: Session = Depends(get_db)):
    lead = institute_outreach_service.get_lead(db, lead_id)
    return ok(institute_outreach_service.lead_out(lead))


@router.patch("/leads/{lead_id}")
def update_lead(lead_id: uuid.UUID, body: LeadProfileIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    lead = institute_outreach_service.get_lead(db, lead_id)
    institute_outreach_service.update_lead_profile(db, lead, body.payload)
    admin_service._audit(db, admin, "outreach.lead.update", None, target_label=lead.display_name)
    db.commit()
    return ok(institute_outreach_service.lead_out(lead))


@router.post("/leads/{lead_id}/complete-profile", summary="Search and crawl web/social sources to enrich lead")
def complete_lead_profile(
    lead_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    limiter.hit("30/hour", "admin-outreach-complete", str(admin.id))
    lead = institute_outreach_service.get_lead(db, lead_id)
    result = institute_lead_complete_service.complete_lead_profile(db, lead)
    admin_service._audit(db, admin, "outreach.lead.complete", None, target_label=lead.display_name)
    db.commit()
    return ok(
        {
            "lead": institute_outreach_service.lead_out(result["lead"]),
            "completion": result["completion"],
        }
    )


@router.post("/leads/{lead_id}/generate-proposal")
def generate_proposal(lead_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    lead = institute_outreach_service.get_lead(db, lead_id)
    institute_outreach_service.generate_proposal(db, lead)
    admin_service._audit(db, admin, "outreach.proposal.generate", None, target_label=lead.display_name)
    db.commit()
    lead = institute_outreach_service.get_lead(db, lead_id)
    return ok(institute_outreach_service.lead_out(lead))


@router.post("/leads/{lead_id}/send")
def send_proposal(
    lead_id: uuid.UUID,
    body: LeadSendIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    mailer: EmailSender = Depends(get_mailer),
    limiter=Depends(get_rate_limiter),
):
    if not body.approve:
        raise AppError("APPROVAL_REQUIRED", "Set approve=true to send outreach.", 422)
    limiter.hit("60/hour", "admin-outreach-send", str(admin.id))
    lead = institute_outreach_service.get_lead(db, lead_id)
    sent = institute_outreach_service.send_outreach(db, lead, body.channels, mailer=mailer)
    admin_service._audit(db, admin, "outreach.send", None, target_label=lead.display_name, channels=body.channels)
    db.commit()
    return ok({"sent": sent, "lead": institute_outreach_service.lead_out(lead)})


@router.post("/leads/{lead_id}/convert")
def convert_lead(
    lead_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    mailer: EmailSender = Depends(get_mailer),
):
    lead = institute_outreach_service.get_lead(db, lead_id)
    result = institute_outreach_service.convert_to_institute(db, lead, mailer=mailer)
    admin_service._audit(db, admin, "outreach.convert", None, target_label=lead.display_name)
    return ok(result)


@router.post("/whatsapp/reset", summary="Restart WhatsApp bridge client (after stale Chrome session)")
def whatsapp_reset(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    from backend.app.services import whatsapp_bridge_client

    result = whatsapp_bridge_client.reset_client()
    data = institute_outreach_service.sync_whatsapp_session(db)
    admin_service._audit(db, admin, "outreach.whatsapp.reset", None, ok=result.get("ok"))
    db.commit()
    return ok({**data, "reset": result})


@router.get("/whatsapp/status")
def whatsapp_status(db: Session = Depends(get_db)):
    data = institute_outreach_service.sync_whatsapp_session(db)
    db.commit()
    return ok(data)


@router.get("/whatsapp/recent-sends")
def whatsapp_recent_sends(db: Session = Depends(get_db), limit: int = Query(15, ge=1, le=50)):
    return ok({"items": institute_outreach_service.recent_whatsapp_sends(db, limit=limit)})


@router.post("/whatsapp/sync-chats")
def whatsapp_sync_chats(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(150, ge=1, le=200),
    limiter=Depends(get_rate_limiter),
):
    limiter.hit("30/hour", "admin-outreach-wa-sync", str(admin.id))
    result = institute_outreach_chat_service.sync_chats_from_bridge(db, chat_limit=limit, message_limit=80)
    admin_service._audit(db, admin, "outreach.whatsapp.sync_chats", None, chats=result.get("chats", 0))
    db.commit()
    return ok(result)


@router.get("/proposal-image", summary="Campus partnership banner used in outreach email and WhatsApp")
def outreach_proposal_image_info(admin: User = Depends(require_admin)):
    return ok(institute_proposal_image_service.proposal_image_info())


@router.post("/proposal-image", summary="Replace campus partnership banner image")
async def outreach_proposal_image_upload(
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limiter=Depends(get_rate_limiter),
):
    limiter.hit("20/hour", "admin-outreach-proposal-image", str(admin.id))
    result = await institute_proposal_image_service.save_proposal_image(file)
    admin_service._audit(db, admin, "outreach.proposal_image", None)
    db.commit()
    return ok(result)


@router.get("/whatsapp/chat-threads")
def whatsapp_chat_threads(
    params: PageParams = Depends(page_params),
    q: str | None = Query(None, max_length=200),
    db: Session = Depends(get_db),
):
    return ok(institute_outreach_chat_service.list_chat_threads(db, params, q=q))


@router.get("/leads/{lead_id}/chat")
def lead_chat(lead_id: uuid.UUID, db: Session = Depends(get_db)):
    lead = institute_outreach_service.get_lead(db, lead_id)
    items = institute_outreach_chat_service.list_chat(db, lead, sync_bridge=False)
    db.commit()
    return ok({"items": items, "whatsapp_phone": lead.whatsapp_phone or ""})


@router.post("/leads/{lead_id}/chat/sync", summary="Pull latest WhatsApp messages for this thread")
def lead_chat_sync(lead_id: uuid.UUID, db: Session = Depends(get_db)):
    lead = institute_outreach_service.get_lead(db, lead_id)
    imported = institute_outreach_chat_service.sync_lead_chat_from_bridge(db, lead, message_limit=200)
    items = institute_outreach_chat_service.list_chat(db, lead, sync_bridge=False)
    db.commit()
    return ok({"imported": imported, "items": items, "whatsapp_phone": lead.whatsapp_phone or ""})


@router.post("/leads/{lead_id}/chat")
def lead_chat_send(
    lead_id: uuid.UUID,
    body: LeadChatIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limiter=Depends(get_rate_limiter),
):
    limiter.hit("120/hour", "admin-outreach-chat", str(admin.id))
    lead = institute_outreach_service.get_lead(db, lead_id)
    if body.channel != "whatsapp":
        raise AppError("NOT_SUPPORTED", "Only WhatsApp chat is supported today.", 422)
    result = institute_outreach_chat_service.send_whatsapp_reply(db, lead, body.text)
    admin_service._audit(db, admin, "outreach.chat.send", None, target_label=lead.display_name)
    db.commit()
    return ok(result)


@router.post("/leads/{lead_id}/chat/attachment", summary="Send WhatsApp message with file attachment")
async def lead_chat_send_attachment(
    lead_id: uuid.UUID,
    file: UploadFile = File(...),
    text: str = Form(""),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limiter=Depends(get_rate_limiter),
):
    limiter.hit("120/hour", "admin-outreach-chat", str(admin.id))
    lead = institute_outreach_service.get_lead(db, lead_id)
    saved: Path | None = None
    try:
        saved, original_name = await institute_outreach_attachment_service.store_outreach_attachment(lead_id, file)
        result = institute_outreach_chat_service.send_whatsapp_reply(
            db,
            lead,
            text,
            attachment_path=str(saved),
            attachment_name=original_name,
        )
        admin_service._audit(db, admin, "outreach.chat.send_attachment", None, target_label=lead.display_name)
        db.commit()
        return ok(result)
    finally:
        if saved is not None:
            saved.unlink(missing_ok=True)


@router.post("/whatsapp/test-send", summary="Send a test WhatsApp message via the bridge")
def whatsapp_test_send(
    body: WhatsappTestSendIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limiter=Depends(get_rate_limiter),
):
    limiter.hit("10/hour", "admin-outreach-wa-test", str(admin.id))
    result = institute_outreach_service.send_whatsapp_test(body.phone, body.text, db)
    admin_service._audit(db, admin, "outreach.whatsapp.test_send", None, phone=body.phone[:8] + "…")
    db.commit()
    return ok({"sent": True, "result": result})
