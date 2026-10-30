import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.api.deps import require_partner
from backend.app.core.database import get_db
from backend.app.core.errors import ok
from backend.app.core.rate_limit import RateLimiter, get_rate_limiter
from backend.app.schemas.partner import CampaignIn, EnrollInstituteIn, PartnerProfileIn, PartnerTaxIn, PayoutIn
from backend.app.services import partner_service

router = APIRouter(prefix="/partner", tags=["partner"])


@router.get("/me")
def me(ctx=Depends(require_partner), db: Session = Depends(get_db)):
    _user, partner = ctx
    return ok(partner_service.partner_out(db, partner))


@router.get("/dashboard")
def dashboard(ctx=Depends(require_partner), db: Session = Depends(get_db)):
    _user, partner = ctx
    return ok(partner_service.dashboard(db, partner))


@router.get("/institutes")
def institutes(ctx=Depends(require_partner), db: Session = Depends(get_db)):
    _user, partner = ctx
    return ok({"items": partner_service.list_institutes(db, partner)})


@router.post("/institutes")
def enroll(body: EnrollInstituteIn, ctx=Depends(require_partner), db: Session = Depends(get_db)):
    _user, partner = ctx
    from backend.app.services import institute_service
    institute = partner_service.enroll_institute(
        db, partner, name=body.name, email=body.email, password=body.password,
        contact_name=body.contact_name, phone=body.phone,
    )
    db.commit()
    return ok(institute_service.institute_out(db, institute))


@router.get("/referrals")
def referrals(ctx=Depends(require_partner), db: Session = Depends(get_db)):
    _user, partner = ctx
    return ok(partner_service.referrals(db, partner))


@router.get("/commissions")
def commissions(ctx=Depends(require_partner), db: Session = Depends(get_db)):
    _user, partner = ctx
    return ok({"items": partner_service.list_commissions(db, partner), "wallet": partner_service.wallet_summary(db, partner.id)})


@router.get("/payouts")
def payouts(ctx=Depends(require_partner), db: Session = Depends(get_db)):
    _user, partner = ctx
    return ok({"items": partner_service.list_payouts(db, partner), "wallet": partner_service.wallet_summary(db, partner.id)})


@router.post("/payouts")
def request_payout(body: PayoutIn, ctx=Depends(require_partner), db: Session = Depends(get_db)):
    _user, partner = ctx
    row = partner_service.request_payout(db, partner, body.amount_cents)
    db.commit()
    return ok(partner_service.payout_out(row))


@router.get("/campaigns")
def campaigns(ctx=Depends(require_partner), db: Session = Depends(get_db)):
    _user, partner = ctx
    return ok({"items": partner_service.list_campaigns(db, partner)})


@router.post("/campaigns")
def create_campaign(body: CampaignIn, ctx=Depends(require_partner), db: Session = Depends(get_db)):
    _user, partner = ctx
    row = partner_service.create_campaign(db, partner, body.name, body.note)
    db.commit()
    return ok(partner_service.campaign_out(partner, row))


@router.get("/marketing")
def marketing(ctx=Depends(require_partner)):
    _user, partner = ctx
    return ok(partner_service.marketing(partner))


@router.get("/links")
def links(ctx=Depends(require_partner), db: Session = Depends(get_db)):
    _user, partner = ctx
    return ok({
        "referral_path": f"/r/{partner.referral_code}",
        "campaigns": partner_service.list_campaigns(db, partner),
    })


@router.put("/profile")
def put_profile(body: PartnerProfileIn, ctx=Depends(require_partner), db: Session = Depends(get_db)):
    _user, partner = ctx
    partner_service.save_profile(db, partner, body.model_dump(exclude_none=True))
    db.commit()
    return ok(partner_service.partner_out(db, partner))


@router.post("/kyc")
async def add_kyc(
    file: UploadFile = File(...),
    note: str = Form(""),
    ctx=Depends(require_partner),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    _user, partner = ctx
    limiter.hit("20/hour", "kyc-upload", str(partner.id))
    await partner_service.add_kyc_upload(db, partner, file, note)
    db.commit()
    return ok(partner_service.partner_out(db, partner))


@router.get("/kyc/{doc_id}/file")
def download_kyc(doc_id: uuid.UUID, ctx=Depends(require_partner)):
    _user, partner = ctx
    path, filename, media_type = partner_service.kyc_stored_file(partner, doc_id)
    return FileResponse(
        path,
        media_type=media_type,
        filename=filename,
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


@router.put("/tax")
def put_tax(body: PartnerTaxIn, ctx=Depends(require_partner), db: Session = Depends(get_db)):
    _user, partner = ctx
    partner_service.save_tax(db, partner, body.model_dump(exclude_none=True))
    db.commit()
    return ok(partner_service.partner_out(db, partner))
