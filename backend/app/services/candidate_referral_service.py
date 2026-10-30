"""Candidate-to-candidate referral codes. Separate from partner → institute /r/ commissions."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.models import User
from backend.app.models.candidate_referral import CandidateReferral
from backend.app.models.partner import Partner


CAND_COOKIE = "ax_cand_ref"
CAND_DAYS = 90


def _now() -> datetime:
    return datetime.now(timezone.utc)


def generate_code(db: Session) -> str:
    for _ in range(12):
        code = "C" + secrets.token_hex(4).upper()
        if db.scalar(select(User.id).where(User.referral_code == code)) is not None:
            continue
        if db.scalar(select(Partner.id).where(Partner.referral_code == code)) is not None:
            continue
        return code
    raise AppError("REFERRAL_CODE_FAILED", "Could not allocate a referral code.", 500)


def ensure_user_code(db: Session, user: User) -> str:
    if user.referral_code:
        return user.referral_code
    user.referral_code = generate_code(db)
    db.flush()
    return user.referral_code


def find_candidate_by_code(db: Session, code: str) -> User | None:
    raw = (code or "").strip().upper()
    if not raw:
        return None
    return db.scalar(select(User).where(func.upper(User.referral_code) == raw))


def capture(db: Session, code: str) -> dict:
    """Resolve /r/{code} for a candidate referrer. Partner codes are handled separately."""
    user = find_candidate_by_code(db, code)
    if user is None:
        raise AppError("REFERRAL_NOT_FOUND", "That referral link is not valid.", 404)
    return {
        "kind": "candidate",
        "referral_code": user.referral_code,
        "organization": "",
        "redirect": "/register",
    }


def attribute_on_register(db: Session, *, referred: User, code: str) -> CandidateReferral | None:
    referrer = find_candidate_by_code(db, code)
    if referrer is None or referrer.id == referred.id:
        return None
    existing = db.scalar(select(CandidateReferral).where(CandidateReferral.referred_user_id == referred.id))
    if existing is not None:
        return existing
    row = CandidateReferral(
        referrer_user_id=referrer.id,
        referred_user_id=referred.id,
        code=(referrer.referral_code or code)[:16],
        status="attributed",
    )
    db.add(row)
    db.flush()
    return row


def mark_converted(db: Session, referred_user_id: uuid.UUID) -> None:
    row = db.scalar(select(CandidateReferral).where(CandidateReferral.referred_user_id == referred_user_id))
    if row is None or row.status == "converted":
        return
    row.status = "converted"
    row.converted_at = _now()
    db.flush()


def summary_for(db: Session, user: User) -> dict:
    code = ensure_user_code(db, user)
    attributed = db.scalar(
        select(func.count()).select_from(CandidateReferral).where(CandidateReferral.referrer_user_id == user.id)
    ) or 0
    converted = db.scalar(
        select(func.count()).select_from(CandidateReferral).where(
            CandidateReferral.referrer_user_id == user.id,
            CandidateReferral.status == "converted",
        )
    ) or 0
    return {
        "referral_code": code,
        "referral_path": f"/r/{code}",
        "attributed": int(attributed),
        "converted": int(converted),
    }
