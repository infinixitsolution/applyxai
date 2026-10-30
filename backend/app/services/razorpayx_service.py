"""RazorpayX partner payouts. Falls back to manual bank transfer when credentials are missing."""

from __future__ import annotations

import logging

import httpx
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.errors import AppError
from backend.app.models import Partner, PartnerPayout, PayoutStatus
from backend.app.services import partner_service
from backend.app.services.payments.base import PaymentError
from backend.app.services.platform_settings_service import get_effective_payments

logger = logging.getLogger("applyxai.payouts")

API_BASE = "https://api.razorpay.com/v1"


def configured() -> bool:
    account = (settings.RAZORPAYX_ACCOUNT_NUMBER or "").strip()
    if not account:
        return False
    key_id = (settings.RAZORPAYX_KEY_ID or "").strip()
    secret = (settings.RAZORPAYX_KEY_SECRET or "").strip()
    if key_id and secret:
        return True
    return False


def _auth(db: Session) -> tuple[str, str, str]:
    account = (settings.RAZORPAYX_ACCOUNT_NUMBER or "").strip()
    key_id = (settings.RAZORPAYX_KEY_ID or "").strip()
    secret = (settings.RAZORPAYX_KEY_SECRET or "").strip()
    if not key_id or not secret:
        eff = get_effective_payments(db)
        if eff.provider == "razorpay" and eff.configured:
            key_id, secret = eff.key_id, eff.key_secret
    if not account or not key_id or not secret:
        raise AppError(
            "PAYOUT_NOT_CONFIGURED",
            "RazorpayX is not configured. Record the bank transfer id in the note, then Mark paid.",
            503,
        )
    return account, key_id, secret


def pay_now(db: Session, payout_id, *, note: str = "") -> PartnerPayout:
    row = db.get(PartnerPayout, payout_id)
    if row is None:
        raise AppError("NOT_FOUND", "Payout not found.", 404)
    if row.status not in (PayoutStatus.APPROVED, PayoutStatus.REQUESTED):
        raise AppError("INVALID_PAYOUT", "Only requested or approved payouts can be paid via RazorpayX.", 422)
    partner = db.get(Partner, row.partner_id)
    if partner is None:
        raise AppError("NOT_FOUND", "Partner not found.", 404)
    if not partner_service.commercial_ready(partner):
        raise AppError("KYC_REQUIRED", "Partner KYC must be verified before paying out.", 409)
    account_no = (partner.payout_account or "").strip()
    ifsc = (partner.payout_ifsc or "").strip()
    if not account_no or not ifsc:
        raise AppError("PAYOUT_ACCOUNT_MISSING", "Partner payout account and IFSC are required.", 422)
    fund_account, key_id, secret = _auth(db)
    payload = {
        "account_number": fund_account,
        "amount": int(row.amount_cents),
        "currency": (row.currency or "INR")[:3],
        "mode": "IMPS",
        "purpose": "payout",
        "queue_if_low_balance": True,
        "reference_id": str(row.id)[:40],
        "narration": "ApplyXAI partner payout",
        "fund_account": {
            "account_type": "bank_account",
            "bank_account": {
                "name": (partner.contact_name or partner.organization or "Partner")[:120],
                "ifsc": ifsc,
                "account_number": account_no,
            },
        },
    }
    try:
        resp = httpx.post(f"{API_BASE}/payouts", json=payload, auth=(key_id, secret), timeout=20)
    except httpx.HTTPError as exc:
        logger.warning("RazorpayX payout failed: %s", type(exc).__name__)
        raise AppError("PAYOUTS_UNAVAILABLE", "Could not reach RazorpayX. Try again or mark paid after a manual transfer.", 502) from exc
    try:
        data = resp.json()
    except ValueError:
        data = {}
    if resp.status_code >= 400:
        desc = ((data.get("error") or {}).get("description")) or "RazorpayX rejected the payout."
        raise AppError("PAYOUT_REJECTED", str(desc)[:300], 502)
    transfer_id = str(data.get("id") or "")
    if not transfer_id:
        raise AppError("PAYOUT_REJECTED", "RazorpayX did not return a transfer id.", 502)
    extra = note.strip()
    status_note = f"RazorpayX {transfer_id}" + (f" — {extra}" if extra else "")
    row = partner_service.set_payout_status(db, row.id, PayoutStatus.PAID, status_note)
    row.provider_transfer_id = transfer_id[:255]
    db.flush()
    return row
