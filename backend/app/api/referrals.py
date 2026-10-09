from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.errors import ok
from backend.app.services import partner_service

router = APIRouter(tags=["referrals"])

REF_COOKIE = "ax_partner_ref"
REF_DAYS = 90


@router.get("/r/{code}")
def capture(code: str, response: Response, c: str | None = Query(None, max_length=32),
            db: Session = Depends(get_db)):
    partner = partner_service.capture_referral(db, code, c)
    db.commit()
    response.set_cookie(
        REF_COOKIE, partner.referral_code, max_age=REF_DAYS * 86400,
        httponly=True, samesite="lax", secure=settings.cookie_secure, path="/",
    )
    return ok({
        "referral_code": partner.referral_code,
        "organization": partner.organization,
        "redirect": "/register/institute",
    })
