"""Partner network: referrals, institute enrollment, commissions, and payouts."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.core.pagination import PageParams, page_response, paginate
from backend.app.core.security import hash_password
from backend.app.models import (
    AssignmentStatus,
    CommissionStatus,
    Institute,
    InstituteAssignment,
    InstituteStatus,
    KycStatus,
    Partner,
    PartnerCommissionMode,
    PartnerAttribution,
    PartnerCampaign,
    PartnerCommission,
    PartnerPayout,
    PartnerStatus,
    Payment,
    PayoutStatus,
    Subscription,
    User,
)

KYC_ELIGIBLE = (KycStatus.VERIFIED, KycStatus.NOT_REQUIRED)
COMMERCIAL = (PartnerStatus.APPROVED, PartnerStatus.ACTIVE)
HELD_PAYOUTS = (PayoutStatus.REQUESTED, PayoutStatus.APPROVED, PayoutStatus.PAID)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _code(db: Session) -> str:
    for _ in range(12):
        code = secrets.token_hex(4).upper()
        if db.scalar(select(Partner.id).where(Partner.referral_code == code)) is None:
            return code
    raise AppError("CODE_COLLISION", "Could not allocate a referral code.", 500)


def partner_for(db: Session, user: User) -> Partner:
    partner = db.scalar(select(Partner).where(Partner.user_id == user.id))
    if partner is None or partner.status == PartnerStatus.CLOSED:
        raise AppError("FORBIDDEN", "This account is not a partner.", 403)
    return partner


def register(
    db: Session,
    user: User,
    *,
    organization: str,
    contact_name: str = "",
    phone: str = "",
    gstin: str = "",
    pan_number: str = "",
) -> Partner:
    if db.scalar(select(Partner.id).where(Partner.user_id == user.id)) is not None:
        raise AppError("ALREADY_PARTNER", "This account is already a partner.", 409)
    organization = organization.strip()
    if not organization:
        raise AppError("PARTNER_ORG_INVALID", "Enter the organisation name.", 422)
    partner = Partner(
        user_id=user.id,
        organization=organization[:190],
        contact_name=(contact_name.strip() or f"{user.first_name} {user.last_name}".strip() or user.email)[:190],
        phone=phone.strip()[:32],
        referral_code=_code(db),
        status=PartnerStatus.PENDING,
        kyc_status=KycStatus.PENDING,
        gstin=gstin.upper().strip()[:15],
        pan_number=pan_number.upper().strip()[:10],
    )
    db.add(partner)
    db.flush()
    return partner


def create_by_admin(
    db: Session,
    *,
    organization: str,
    email: str,
    password: str,
    contact_name: str = "",
    phone: str = "",
    approve: bool = True,
    commission_mode: PartnerCommissionMode = PartnerCommissionMode.PERCENT_PAYMENT,
    commission_bps: int = 2000,
    commission_flat_cents: int = 0,
) -> Partner:
    """Create a partner and its login. The contact can sign in immediately."""
    from backend.app.services.auth_service import normalize_email
    email = normalize_email(email)
    if password.lower() == email:
        raise AppError("WEAK_PASSWORD", "Password must not be the email address.", 422)
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise AppError("EMAIL_TAKEN", "That email already has an account.", 409)
    contact_name = contact_name.strip()
    first, _, last = contact_name.partition(" ")
    user = User(
        email=email,
        password_hash=hash_password(password),
        first_name=(first or organization)[:100],
        last_name=last.strip()[:100],
        is_verified=True,
    )
    db.add(user)
    db.flush()
    partner = register(
        db, user, organization=organization, contact_name=contact_name or organization, phone=phone,
    )
    partner.commission_mode = commission_mode
    partner.commission_bps = max(0, min(int(commission_bps), 10_000))
    partner.commission_flat_cents = max(0, int(commission_flat_cents))
    if approve:
        partner.status = PartnerStatus.APPROVED
        partner.kyc_status = KycStatus.NOT_REQUIRED
        db.flush()
    return partner


def partner_out(db: Session, partner: Partner) -> dict:
    wallet = wallet_summary(db, partner.id)
    return {
        "id": str(partner.id),
        "user_id": str(partner.user_id),
        "organization": partner.organization,
        "contact_name": partner.contact_name,
        "phone": partner.phone,
        "referral_code": partner.referral_code,
        "status": partner.status.value,
        "kyc_status": partner.kyc_status.value,
        "commission_mode": partner.commission_mode.value,
        "commission_bps": partner.commission_bps,
        "commission_flat_cents": partner.commission_flat_cents,
        "gstin": partner.gstin,
        "pan_number": partner.pan_number,
        "payout_account": partner.payout_account,
        "payout_ifsc": partner.payout_ifsc,
        "kyc_documents": partner.kyc_documents or [],
        "click_count": partner.click_count,
        "wallet": wallet,
        "created_at": _iso(partner.created_at),
    }


def wallet_summary(db: Session, partner_id: uuid.UUID) -> dict:
    accrued = db.scalar(select(func.coalesce(func.sum(PartnerCommission.amount_cents), 0)).where(
        PartnerCommission.partner_id == partner_id,
        PartnerCommission.status == CommissionStatus.ACCRUED,
    )) or 0
    approved = db.scalar(select(func.coalesce(func.sum(PartnerCommission.amount_cents), 0)).where(
        PartnerCommission.partner_id == partner_id,
        PartnerCommission.status == CommissionStatus.APPROVED,
    )) or 0
    held = db.scalar(select(func.coalesce(func.sum(PartnerPayout.amount_cents), 0)).where(
        PartnerPayout.partner_id == partner_id,
        PartnerPayout.status.in_(HELD_PAYOUTS),
    )) or 0
    available = max(approved - held, 0)
    return {"accrued_cents": int(accrued), "approved_cents": int(approved), "available_cents": int(available)}


def find_by_code(db: Session, code: str) -> Partner | None:
    code = (code or "").strip().upper()
    if not code:
        return None
    partner = db.scalar(select(Partner).where(Partner.referral_code == code))
    if partner is None or partner.status not in (*COMMERCIAL, PartnerStatus.PENDING):
        return None
    return partner


def capture_referral(db: Session, code: str, campaign_code: str | None = None) -> Partner:
    partner = find_by_code(db, code)
    if partner is None:
        raise AppError("REFERRAL_NOT_FOUND", "That referral link is not valid.", 404)
    partner.click_count += 1
    if campaign_code:
        campaign = db.scalar(select(PartnerCampaign).where(
            PartnerCampaign.partner_id == partner.id,
            PartnerCampaign.code == campaign_code.strip().upper(),
        ))
        if campaign is not None:
            campaign.click_count += 1
    db.flush()
    return partner


def attribute_institute(db: Session, partner_id: uuid.UUID, institute_id: uuid.UUID, source: str = "referral") -> None:
    existing = db.scalar(select(PartnerAttribution).where(
        PartnerAttribution.partner_id == partner_id,
        PartnerAttribution.institute_id == institute_id,
    ))
    if existing is None:
        db.add(PartnerAttribution(partner_id=partner_id, institute_id=institute_id, source=source))
        db.flush()


def _login_out(user: User | None) -> dict | None:
    if user is None:
        return None
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "last_login_at": _iso(user.last_login_at),
        "created_at": _iso(user.created_at),
    }


def _commission_admin_out(db: Session, row: PartnerCommission) -> dict:
    out = commission_out(row)
    institute = db.get(Institute, row.institute_id) if row.institute_id else None
    out["institute_name"] = institute.name if institute else None
    return out


def _counts(db: Session, model, partner_id: uuid.UUID, enum_cls) -> dict:
    by = {status.value: 0 for status in enum_cls}
    for status, n in db.execute(
        select(model.status, func.count()).where(model.partner_id == partner_id).group_by(model.status)
    ):
        by[status.value if hasattr(status, "value") else status] = n
    return by


def admin_detail(db: Session, partner: Partner) -> dict:
    """Full partner record for the admin partner dashboard."""
    dash = dashboard(db, partner)
    commissions = db.scalars(
        select(PartnerCommission).where(PartnerCommission.partner_id == partner.id)
        .order_by(PartnerCommission.created_at.desc()).limit(50)
    ).all()
    inst_by = {status.value: 0 for status in InstituteStatus}
    for status, n in db.execute(
        select(Institute.status, func.count()).where(Institute.partner_id == partner.id).group_by(Institute.status)
    ):
        inst_by[status.value if hasattr(status, "value") else status] = n
    return {
        **dash,
        "login": _login_out(partner_user(db, partner)),
        "institute_list": list_institutes(db, partner),
        "commissions": [_commission_admin_out(db, row) for row in commissions],
        "payouts": list_payouts(db, partner),
        "campaigns": list_campaigns(db, partner),
        "reports": {
            "institutes_by_status": inst_by,
            "commissions_by_status": _counts(db, PartnerCommission, partner.id, CommissionStatus),
            "payouts_by_status": _counts(db, PartnerPayout, partner.id, PayoutStatus),
        },
    }


def dashboard(db: Session, partner: Partner) -> dict:
    institutes = db.scalar(select(func.count()).select_from(Institute).where(Institute.partner_id == partner.id)) or 0
    recent = db.scalars(select(Institute).where(Institute.partner_id == partner.id)
                        .order_by(Institute.created_at.desc()).limit(8)).all()
    commissions = db.scalars(select(PartnerCommission).where(PartnerCommission.partner_id == partner.id)
                             .order_by(PartnerCommission.created_at.desc()).limit(8)).all()
    from backend.app.services import institute_service
    return {
        "partner": partner_out(db, partner),
        "institutes": institutes,
        "recent_institutes": [institute_service.institute_out(db, i) for i in recent],
        "recent_commissions": [commission_out(c) for c in commissions],
        "referral_path": f"/r/{partner.referral_code}",
    }


def enroll_institute(
    db: Session,
    partner: Partner,
    *,
    name: str,
    email: str,
    password: str,
    contact_name: str = "",
    phone: str = "",
) -> Institute:
    if partner.status not in COMMERCIAL:
        raise AppError("PARTNER_NOT_APPROVED", "Your partner account must be approved first.", 403)
    email = email.strip().lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise AppError("EMAIL_TAKEN", "That email already has an account.", 409)
    from backend.app.models import InstituteStatus
    from backend.app.services import institute_service
    from backend.app.services.auth_service import normalize_email
    user = User(
        email=normalize_email(email),
        password_hash=hash_password(password),
        first_name=contact_name.split(" ", 1)[0][:100] if contact_name else "",
        last_name=(contact_name.split(" ", 1)[1] if contact_name and " " in contact_name else "")[:100],
        is_verified=True,
    )
    db.add(user)
    db.flush()
    institute = institute_service.register(
        db, user, name=name, contact_name=contact_name or name, phone=phone,
        partner_id=partner.id, source="partner", status=InstituteStatus.PENDING,
    )
    attribute_institute(db, partner.id, institute.id, source="enroll")
    return institute


def list_institutes(db: Session, partner: Partner) -> list[dict]:
    from backend.app.services import institute_service
    rows = db.scalars(select(Institute).where(Institute.partner_id == partner.id)
                      .order_by(Institute.created_at.desc())).all()
    return [institute_service.institute_out(db, r) for r in rows]


def referrals(db: Session, partner: Partner) -> dict:
    return {
        "referral_code": partner.referral_code,
        "referral_path": f"/r/{partner.referral_code}",
        "click_count": partner.click_count,
        "institutes": list_institutes(db, partner),
    }


def set_status(db: Session, partner: Partner, status: PartnerStatus) -> Partner:
    partner.status = status
    if status in COMMERCIAL and partner.kyc_status == KycStatus.PENDING:
        pass
    db.flush()
    return partner


def set_kyc(db: Session, partner: Partner, status: KycStatus) -> Partner:
    partner.kyc_status = status
    db.flush()
    return partner


def add_kyc_document(db: Session, partner: Partner, filename: str, note: str = "") -> Partner:
    docs = list(partner.kyc_documents or [])
    docs.append({"filename": filename.strip()[:255], "note": note.strip()[:255], "uploaded_at": _now().isoformat()})
    partner.kyc_documents = docs
    db.flush()
    return partner


def update_by_admin(
    db: Session,
    partner: Partner,
    *,
    organization: str,
    contact_name: str = "",
    phone: str = "",
    commission_mode: PartnerCommissionMode,
    commission_bps: int,
    commission_flat_cents: int = 0,
    status: PartnerStatus,
    kyc_status: KycStatus,
    gstin: str = "",
    pan_number: str = "",
    payout_account: str = "",
    payout_ifsc: str = "",
    email: str | None = None,
) -> Partner:
    from backend.app.services.auth_service import normalize_email

    partner.organization = organization.strip()[:190]
    partner.contact_name = (contact_name or "").strip()[:190]
    partner.phone = str(phone or "")[:32]
    partner.commission_mode = commission_mode
    partner.commission_bps = max(0, min(int(commission_bps), 10_000))
    partner.commission_flat_cents = max(0, int(commission_flat_cents))
    partner.status = status
    partner.kyc_status = kyc_status
    save_tax(
        db,
        partner,
        {
            "gstin": gstin,
            "pan_number": pan_number,
            "payout_account": payout_account,
            "payout_ifsc": payout_ifsc,
        },
    )
    if email is not None:
        email_norm = normalize_email(email)
        user = partner_user(db, partner)
        if user is None:
            raise AppError("NO_USER", "This partner has no login to attach an email to.", 400)
        if user.email != email_norm:
            if db.scalar(select(User.id).where(User.email == email_norm, User.id != user.id)) is not None:
                raise AppError("EMAIL_TAKEN", "That email already has an account.", 409)
            user.email = email_norm
            contact = partner.contact_name.strip()
            if contact:
                first, _, last = contact.partition(" ")
                user.first_name = (first or partner.organization)[:100]
                user.last_name = last.strip()[:100]
    db.flush()
    return partner


def save_profile(db: Session, partner: Partner, body: dict) -> Partner:
    if org := (body.get("organization") or "").strip():
        partner.organization = org[:190]
    if contact := (body.get("contact_name") or "").strip():
        partner.contact_name = contact[:190]
    if "phone" in body:
        partner.phone = str(body.get("phone") or "")[:32]
    db.flush()
    return partner


def save_tax(db: Session, partner: Partner, body: dict) -> Partner:
    if "gstin" in body:
        partner.gstin = str(body.get("gstin") or "").upper()[:15]
    if "pan_number" in body:
        partner.pan_number = str(body.get("pan_number") or "").upper()[:10]
    if "payout_account" in body:
        partner.payout_account = str(body.get("payout_account") or "")[:255]
    if "payout_ifsc" in body:
        partner.payout_ifsc = str(body.get("payout_ifsc") or "").upper()[:20]
    db.flush()
    return partner


def commercial_ready(partner: Partner) -> bool:
    return partner.status in COMMERCIAL and partner.kyc_status in KYC_ELIGIBLE


def _payment_commission(db: Session, partner: Partner, payment: Payment, sub: Subscription, institute: Institute) -> tuple[int, str] | None:
    mode = partner.commission_mode
    if mode == PartnerCommissionMode.FLAT_CANDIDATE:
        return None
    if mode == PartnerCommissionMode.PERCENT_PAYMENT:
        amount = max(0, int(payment.amount_cents * partner.commission_bps / 10_000))
        note = f"{institute.name} payment ({partner.commission_bps / 100:g}% of payment)"
    elif mode == PartnerCommissionMode.FLAT_PAYMENT:
        amount = max(0, int(partner.commission_flat_cents))
        note = f"{institute.name} payment (flat per payment)"
    elif mode == PartnerCommissionMode.FLAT_SEAT:
        from backend.app.services import institute_service

        seats = max(1, institute_service.seat_count_for_plan(sub.plan) if sub.plan else 1)
        amount = max(0, int(partner.commission_flat_cents) * seats)
        note = f"{institute.name} payment ({seats} seat{'s' if seats != 1 else ''} × flat rate)"
    else:
        return None
    if amount <= 0:
        return None
    return amount, note[:255]


def _commission_snapshot(partner: Partner) -> tuple[PartnerCommissionMode, int, int]:
    return partner.commission_mode, partner.commission_bps, partner.commission_flat_cents


def maybe_accrue_commission(db: Session, payment: Payment, sub: Subscription | None) -> PartnerCommission | None:
    if sub is None or sub.institute_id is None or payment is None:
        return None
    if (sub.provider or "") == "admin":
        return None
    if not payment.amount_cents or (payment.status or "").lower() not in ("paid", "captured", "authorized", "success"):
        return None
    if db.scalar(select(PartnerCommission.id).where(PartnerCommission.payment_id == payment.id)):
        return None
    institute = db.get(Institute, sub.institute_id)
    if institute is None or institute.partner_id is None:
        return None
    partner = db.get(Partner, institute.partner_id)
    if partner is None or not commercial_ready(partner):
        return None
    computed = _payment_commission(db, partner, payment, sub, institute)
    if computed is None:
        return None
    amount, note = computed
    mode, rate_bps, rate_flat = _commission_snapshot(partner)
    row = PartnerCommission(
        partner_id=partner.id,
        institute_id=institute.id,
        subscription_id=sub.id,
        payment_id=payment.id,
        amount_cents=amount,
        currency=payment.currency or "INR",
        commission_mode=mode,
        rate_bps=rate_bps,
        rate_flat_cents=rate_flat,
        status=CommissionStatus.ACCRUED,
        note=note,
    )
    db.add(row)
    db.flush()
    _notify_commission(db, partner, row)
    return row


def _notify_commission(db: Session, partner: Partner, row: PartnerCommission) -> None:
    from backend.app.services import notification_service

    if partner.user_id is None:
        return
    amount = row.amount_cents / 100
    currency = row.currency or "INR"
    notification_service.notify_event(
        db,
        partner.user_id,
        "partner_commission",
        link="/partner/commissions",
        variables={
            "amount": f"{amount:.2f}",
            "currency": currency,
            "message": f"You earned {currency} {amount:.2f} in commission. {row.note or ''}".strip(),
        },
    )


def maybe_accrue_candidate_commission(db: Session, assignment: InstituteAssignment) -> PartnerCommission | None:
    if assignment.status != AssignmentStatus.ACTIVE:
        return None
    if db.scalar(select(PartnerCommission.id).where(PartnerCommission.assignment_id == assignment.id)):
        return None
    institute = db.get(Institute, assignment.institute_id)
    if institute is None or institute.partner_id is None:
        return None
    partner = db.get(Partner, institute.partner_id)
    if partner is None or not commercial_ready(partner):
        return None
    if partner.commission_mode != PartnerCommissionMode.FLAT_CANDIDATE:
        return None
    amount = max(0, int(partner.commission_flat_cents))
    if amount <= 0:
        return None
    mode, rate_bps, rate_flat = _commission_snapshot(partner)
    note = f"{institute.name} candidate {assignment.candidate_email} (active seat)"
    row = PartnerCommission(
        partner_id=partner.id,
        institute_id=institute.id,
        assignment_id=assignment.id,
        amount_cents=amount,
        currency="INR",
        commission_mode=mode,
        rate_bps=rate_bps,
        rate_flat_cents=rate_flat,
        status=CommissionStatus.ACCRUED,
        note=note[:255],
    )
    db.add(row)
    db.flush()
    return row


def commission_out(row: PartnerCommission) -> dict:
    return {
        "id": str(row.id),
        "institute_id": str(row.institute_id) if row.institute_id else None,
        "amount_cents": row.amount_cents,
        "currency": row.currency,
        "commission_mode": row.commission_mode.value,
        "rate_bps": row.rate_bps,
        "rate_flat_cents": row.rate_flat_cents,
        "status": row.status.value,
        "note": row.note,
        "created_at": _iso(row.created_at),
    }


def list_commissions(db: Session, partner: Partner) -> list[dict]:
    rows = db.scalars(select(PartnerCommission).where(PartnerCommission.partner_id == partner.id)
                      .order_by(PartnerCommission.created_at.desc())).all()
    return [commission_out(r) for r in rows]


def set_commission_status(db: Session, commission_id: uuid.UUID, status: CommissionStatus) -> PartnerCommission:
    row = db.get(PartnerCommission, commission_id)
    if row is None:
        raise AppError("NOT_FOUND", "Commission not found.", 404)
    row.status = status
    db.flush()
    return row


def request_payout(db: Session, partner: Partner, amount_cents: int | None = None) -> PartnerPayout:
    if not commercial_ready(partner):
        raise AppError("KYC_REQUIRED", "KYC must be verified before requesting a payout.", 403)
    wallet = wallet_summary(db, partner.id)
    amount = amount_cents if amount_cents is not None else wallet["available_cents"]
    if amount <= 0 or amount > wallet["available_cents"]:
        raise AppError("INVALID_PAYOUT", "There isn't enough approved commission for that payout.", 422)
    row = PartnerPayout(partner_id=partner.id, amount_cents=amount, currency="INR", status=PayoutStatus.REQUESTED)
    db.add(row)
    db.flush()
    return row


def payout_out(row: PartnerPayout) -> dict:
    return {
        "id": str(row.id),
        "amount_cents": row.amount_cents,
        "currency": row.currency,
        "status": row.status.value,
        "note": row.note,
        "processed_at": _iso(row.processed_at),
        "created_at": _iso(row.created_at),
    }


def list_payouts(db: Session, partner: Partner) -> list[dict]:
    rows = db.scalars(select(PartnerPayout).where(PartnerPayout.partner_id == partner.id)
                      .order_by(PartnerPayout.created_at.desc())).all()
    return [payout_out(r) for r in rows]


def set_payout_status(db: Session, payout_id: uuid.UUID, status: PayoutStatus, note: str = "") -> PartnerPayout:
    row = db.get(PartnerPayout, payout_id)
    if row is None:
        raise AppError("NOT_FOUND", "Payout not found.", 404)
    row.status = status
    if note:
        row.note = note[:500]
    if status in (PayoutStatus.APPROVED, PayoutStatus.PAID, PayoutStatus.REJECTED):
        row.processed_at = _now()
    db.flush()
    return row


def create_campaign(db: Session, partner: Partner, name: str, note: str = "") -> PartnerCampaign:
    name = name.strip()
    if not name:
        raise AppError("CAMPAIGN_NAME_INVALID", "Enter a campaign name.", 422)
    code = secrets.token_hex(3).upper()
    row = PartnerCampaign(partner_id=partner.id, name=name[:120], code=code, note=note.strip()[:255])
    db.add(row)
    db.flush()
    return row


def campaign_out(partner: Partner, row: PartnerCampaign) -> dict:
    return {
        "id": str(row.id),
        "name": row.name,
        "code": row.code,
        "click_count": row.click_count,
        "note": row.note,
        "path": f"/r/{partner.referral_code}?c={row.code}",
        "created_at": _iso(row.created_at),
    }


def list_campaigns(db: Session, partner: Partner) -> list[dict]:
    rows = db.scalars(select(PartnerCampaign).where(PartnerCampaign.partner_id == partner.id)
                      .order_by(PartnerCampaign.created_at.desc())).all()
    return [campaign_out(partner, r) for r in rows]


def marketing(partner: Partner) -> dict:
    return {
        "referral_path": f"/r/{partner.referral_code}",
        "assets": [
            {"title": "Institute signup", "text": "Share your referral link with training institutes."},
            {"title": "Campus seats", "text": "Institutes buy seats; you earn commission on verified payments."},
        ],
    }


def list_partners(db: Session, params: PageParams, q: str | None = None, status: PartnerStatus | None = None) -> dict:
    stmt = select(Partner).order_by(Partner.created_at.desc())
    if status is not None:
        stmt = stmt.where(Partner.status == status)
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(Partner.organization).like(like), func.lower(Partner.referral_code).like(like)))
    rows, total = paginate(db, stmt, params)
    return page_response([partner_out(db, r) for r in rows], total, params)


def get_partner(db: Session, partner_id: uuid.UUID) -> Partner:
    partner = db.get(Partner, partner_id)
    if partner is None:
        raise AppError("NOT_FOUND", "Partner not found.", 404)
    return partner


def partner_user(db: Session, partner: Partner) -> User | None:
    return db.get(User, partner.user_id)
