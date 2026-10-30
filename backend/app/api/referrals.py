from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.errors import AppError, ok
from backend.app.models import User
from backend.app.services import candidate_referral_service, partner_service

router = APIRouter(tags=["referrals"])

REF_COOKIE = "ax_partner_ref"
REF_DAYS = 90


@router.get("/r/{code}")
def capture(code: str, response: Response, c: str | None = Query(None, max_length=32),
            db: Session = Depends(get_db)):
    try:
        partner = partner_service.capture_referral(db, code, c)
    except AppError as exc:
        if getattr(exc, "code", "") != "REFERRAL_NOT_FOUND":
            raise
        data = candidate_referral_service.capture(db, code)
        db.commit()
        response.set_cookie(
            candidate_referral_service.CAND_COOKIE, data["referral_code"],
            max_age=candidate_referral_service.CAND_DAYS * 86400,
            httponly=True, samesite="lax", secure=settings.cookie_secure, path="/",
        )
        return ok(data)
    db.commit()
    response.set_cookie(
        REF_COOKIE, partner.referral_code, max_age=REF_DAYS * 86400,
        httponly=True, samesite="lax", secure=settings.cookie_secure, path="/",
    )
    return ok({
        "kind": "partner",
        "referral_code": partner.referral_code,
        "organization": partner.organization,
        "redirect": "/register/institute",
    })


@router.get("/referrals/me")
def my_candidate_referral(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = candidate_referral_service.summary_for(db, user)
    db.commit()
    return ok(data)
