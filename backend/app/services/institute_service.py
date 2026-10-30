"""Training-institute workspace: seats, student invites, and entitlements."""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.core.pagination import PageParams, page_response, paginate
from backend.app.core.plans import PLAN_LIMITS
from backend.app.core.security import generate_token, hash_password, hash_token
from backend.app.models import (
    Application,
    ApplicationStatus,
    AssignmentStatus,
    Institute,
    InstituteAssignment,
    InstituteInvite,
    InstituteMember,
    InstituteMemberRole,
    InstituteSeat,
    InstituteStatus,
    OPEN_ASSIGNMENT_STATUSES,
    Partner,
    PartnerCommission,
    Payment,
    Plan,
    PlanKind,
    SeatStatus,
    Subscription,
    SubscriptionStatus,
    User,
)
from backend.app.services import billing_service, gst_service

INSTITUTE_TYPES = (
    "TRAINING_CENTRE", "COLLEGE", "SCHOOL", "IT_TRAINING", "COACHING",
    "UNIVERSITY", "CORPORATE_LEARNING", "OTHER",
)

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
DEFAULT_SETTINGS = {
    "timezone": "Asia/Kolkata",
    "notify_invites": True,
    "notify_acceptances": True,
    "notify_low_seats": True,
    "low_seat_threshold": 3,
    "invite_expiry_days": 7,
    "invite_note": "",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _validate_tax(gstin: str, pan: str) -> tuple[str, str]:
    try:
        gstin = gst_service.validate_gstin(gstin)
    except AppError as exc:
        if exc.code == "GSTIN_INVALID":
            raise AppError("INSTITUTE_GSTIN_INVALID", exc.message, exc.status) from exc
        raise
    pan = pan.upper().strip()
    if pan and PAN_RE.match(pan) is None:
        raise AppError("INSTITUTE_PAN_INVALID", "Enter a valid PAN.", 422)
    return gstin, pan


def membership_for(db: Session, user: User) -> tuple[Institute, InstituteMember]:
    row = db.execute(
        select(InstituteMember, Institute)
        .join(Institute, Institute.id == InstituteMember.institute_id)
        .where(
            InstituteMember.user_id == user.id,
            InstituteMember.status == "active",
            Institute.status != InstituteStatus.CLOSED,
        )
        .order_by(Institute.created_at.desc())
        .limit(1)
    ).first()
    if row is None:
        raise AppError("FORBIDDEN", "This account is not linked to an institute.", 403)
    member, institute = row
    return institute, member


def require_active(institute: Institute) -> None:
    if institute.status != InstituteStatus.ACTIVE:
        raise AppError("INSTITUTE_NOT_ACTIVE", "This institute must be approved before you can do that.", 403)


def require_admin_member(member: InstituteMember) -> None:
    if member.role != InstituteMemberRole.ADMIN:
        raise AppError("FORBIDDEN", "Only an institute admin can do that.", 403)


def register(
    db: Session,
    user: User,
    *,
    name: str,
    contact_name: str,
    phone: str = "",
    institute_type: str = "OTHER",
    gstin: str = "",
    pan_number: str = "",
    partner_id: uuid.UUID | None = None,
    source: str = "direct",
    status: InstituteStatus = InstituteStatus.PENDING,
) -> Institute:
    name = name.strip()
    if not name or len(name) > 190:
        raise AppError("INSTITUTE_NAME_INVALID", "Enter the institute name.", 422)
    contact_name = contact_name.strip() or f"{user.first_name} {user.last_name}".strip() or user.email
    itype = institute_type.upper().strip() or "OTHER"
    if itype not in INSTITUTE_TYPES:
        itype = "OTHER"
    gstin, pan_number = _validate_tax(gstin, pan_number)
    institute = Institute(
        name=name,
        email=user.email,
        contact_name=contact_name,
        phone=phone.strip()[:32],
        institute_type=itype,
        gstin=gstin,
        pan_number=pan_number,
        status=status,
        partner_id=partner_id,
        source=source,
        claimed_by_user_id=user.id,
        settings=dict(DEFAULT_SETTINGS),
    )
    db.add(institute)
    db.flush()
    db.add(InstituteMember(institute_id=institute.id, user_id=user.id, role=InstituteMemberRole.ADMIN))
    db.flush()
    if partner_id is not None:
        from backend.app.services import partner_service
        partner_service.attribute_institute(db, partner_id, institute.id, source="referral")
    return institute


def create_by_admin(
    db: Session,
    *,
    name: str,
    email: str,
    password: str,
    contact_name: str = "",
    phone: str = "",
    approve: bool = True,
) -> Institute:
    """Create an institute and its admin login. The contact can sign in immediately."""
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
        first_name=(first or name)[:100],
        last_name=last.strip()[:100],
        is_verified=True,
    )
    db.add(user)
    db.flush()
    return register(
        db, user,
        name=name,
        contact_name=contact_name or name,
        phone=phone,
        source="admin",
        status=InstituteStatus.ACTIVE if approve else InstituteStatus.PENDING,
    )


def institute_out(db: Session, institute: Institute) -> dict:
    counts = seat_counts(db, institute.id)
    return {
        "id": str(institute.id),
        "name": institute.name,
        "email": institute.email,
        "contact_name": institute.contact_name,
        "phone": institute.phone,
        "institute_type": institute.institute_type,
        "gstin": institute.gstin,
        "pan_number": institute.pan_number,
        "status": institute.status.value,
        "partner_id": str(institute.partner_id) if institute.partner_id else None,
        "source": institute.source,
        "settings": {**DEFAULT_SETTINGS, **(institute.settings or {})},
        "seats": counts,
        "created_at": _iso(institute.created_at),
    }


def seat_counts(db: Session, institute_id: uuid.UUID) -> dict:
    rows = db.execute(
        select(InstituteSeat.status, func.count()).where(InstituteSeat.institute_id == institute_id)
        .group_by(InstituteSeat.status)
    ).all()
    by = {status.value: 0 for status in SeatStatus}
    for status, n in rows:
        by[status.value if hasattr(status, "value") else status] = n
    available = by[SeatStatus.PURCHASED.value]
    assigned = by[SeatStatus.ASSIGNED.value]
    return {"total": sum(by.values()), "available": available, "assigned": assigned, "by_status": by}


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


def _partner_brief(partner: Partner) -> dict:
    return {
        "id": str(partner.id),
        "organization": partner.organization,
        "referral_code": partner.referral_code,
        "status": partner.status.value,
        "kyc_status": partner.kyc_status.value,
    }


def _members_out(db: Session, institute: Institute) -> list[dict]:
    rows = db.scalars(
        select(InstituteMember).where(InstituteMember.institute_id == institute.id)
        .order_by(InstituteMember.created_at.asc())
    ).all()
    out = []
    for member in rows:
        user = db.get(User, member.user_id)
        out.append({
            "id": str(member.id),
            "user_id": str(member.user_id),
            "email": user.email if user else "",
            "name": " ".join(part for part in ((user.first_name if user else ""), (user.last_name if user else "")) if part).strip(),
            "role": member.role.value,
            "status": member.status,
        })
    return out


def admin_detail(db: Session, institute: Institute) -> dict:
    """Full campus record for the admin institute dashboard."""
    dash = dashboard(db, institute)
    login = admin_user(db, institute)
    partner = db.get(Partner, institute.partner_id) if institute.partner_id else None
    assignments = db.scalars(
        select(InstituteAssignment).where(InstituteAssignment.institute_id == institute.id)
        .order_by(InstituteAssignment.created_at.desc()).limit(50)
    ).all()
    subs = db.scalars(
        select(Subscription).where(Subscription.institute_id == institute.id)
        .order_by(Subscription.created_at.desc()).limit(20)
    ).all()
    payments = db.scalars(
        select(Payment).join(Subscription, Payment.subscription_id == Subscription.id)
        .where(Subscription.institute_id == institute.id)
        .order_by(Payment.created_at.desc()).limit(20)
    ).all()
    commissions = db.scalars(
        select(PartnerCommission).where(PartnerCommission.institute_id == institute.id)
        .order_by(PartnerCommission.created_at.desc()).limit(20)
    ).all()
    return {
        "institute": dash["institute"],
        "dashboard": dash,
        "login": _login_out(login),
        "partner": _partner_brief(partner) if partner else None,
        "subscription": dash["subscription"],
        "subscriptions": [billing_service.sub_out(s) for s in subs],
        "payments": [billing_service.payment_out(p) for p in payments],
        "students": [assignment_out(a, db) for a in assignments],
        "invitations": list_invites(db, institute),
        "seats": {"counts": dash["seats"], "items": list_seats(db, institute)},
        "reports": reports(db, institute),
        "members": _members_out(db, institute),
        "commissions": [{
            "id": str(row.id),
            "institute_id": str(row.institute_id) if row.institute_id else None,
            "amount_cents": row.amount_cents,
            "currency": row.currency,
            "rate_bps": row.rate_bps,
            "status": row.status.value,
            "note": row.note,
            "created_at": _iso(row.created_at),
        } for row in commissions],
    }


def dashboard(db: Session, institute: Institute) -> dict:
    counts = seat_counts(db, institute.id)
    students = db.scalar(select(func.count()).select_from(InstituteAssignment).where(
        InstituteAssignment.institute_id == institute.id,
        InstituteAssignment.status == AssignmentStatus.ACTIVE,
    )) or 0
    pending = db.scalar(select(func.count()).select_from(InstituteAssignment).where(
        InstituteAssignment.institute_id == institute.id,
        InstituteAssignment.status.in_((AssignmentStatus.INVITED, AssignmentStatus.PENDING_CANDIDATE_ACCEPTANCE)),
    )) or 0
    sub = current_subscription(db, institute.id)
    recent = db.scalars(
        select(InstituteAssignment).where(InstituteAssignment.institute_id == institute.id)
        .order_by(InstituteAssignment.created_at.desc()).limit(8)
    ).all()
    return {
        "institute": institute_out(db, institute),
        "subscription": billing_service.sub_out(sub),
        "students": students,
        "pending_invites": pending,
        "seats": counts,
        "activity": student_activity(db, institute.id),
        "recent_assignments": [assignment_out(a, db) for a in recent],
    }


def active_student_user_ids(db: Session, institute_id: uuid.UUID) -> list[uuid.UUID]:
    return list(db.scalars(
        select(InstituteAssignment.student_user_id).where(
            InstituteAssignment.institute_id == institute_id,
            InstituteAssignment.status == AssignmentStatus.ACTIVE,
            InstituteAssignment.student_user_id.is_not(None),
        )
    ).all())


def student_activity(db: Session, institute_id: uuid.UUID) -> dict:
    """Campus-wide jobs searched, applied, skipped, and failed for active students."""
    from backend.app.services.dashboard_service import CHART_DAYS, daily_series

    user_ids = active_student_user_ids(db, institute_id)
    by_status = {s.value: 0 for s in ApplicationStatus}
    if user_ids:
        for status, count in db.execute(
            select(Application.status, func.count())
            .where(Application.user_id.in_(user_ids))
            .group_by(Application.status)
        ):
            by_status[status.value] = count
    applied = by_status["applied"]
    failed = by_status["failed"]
    now = datetime.now(timezone.utc)
    today = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    chart_start = today - timedelta(days=CHART_DAYS - 1)
    if user_ids:
        series = daily_series(db, chart_start, Application.user_id.in_(user_ids))
        daily = [{"date": day, **counts} for day, counts in series.items()]
    else:
        daily = [
            {"date": (chart_start + timedelta(days=i)).date().isoformat(), "applied": 0, "failed": 0}
            for i in range(CHART_DAYS)
        ]
    return {
        "searched": sum(by_status.values()),
        "applied": applied,
        "skipped": by_status["skipped"],
        "failed": failed,
        "success_rate": round(applied / (applied + failed), 4) if applied + failed else None,
        "daily": daily,
    }


def current_subscription(db: Session, institute_id: uuid.UUID) -> Subscription | None:
    now = _now()
    subs = db.scalars(
        select(Subscription).where(
            Subscription.institute_id == institute_id,
            Subscription.status.in_(billing_service.ENTITLED),
        ).order_by(Subscription.created_at.desc())
    ).all()
    return next((s for s in subs if billing_service._entitled(s, now)), None)


def seat_count_for_plan(plan: Plan) -> int:
    limits = {**PLAN_LIMITS.get(plan.code, {}), **(plan.limits or {})}
    try:
        return max(1, int(limits.get("seats") or 1))
    except (TypeError, ValueError):
        return 1


def ensure_seats_for_subscription(db: Session, sub: Subscription) -> int:
    if sub.institute_id is None or sub.status not in billing_service.ENTITLED:
        return 0
    existing = db.scalar(select(func.count()).select_from(InstituteSeat).where(
        InstituteSeat.subscription_id == sub.id
    )) or 0
    needed = seat_count_for_plan(sub.plan) - existing
    for _ in range(max(0, needed)):
        db.add(InstituteSeat(institute_id=sub.institute_id, subscription_id=sub.id, status=SeatStatus.PURCHASED))
    if needed > 0:
        db.flush()
    return max(0, needed)


def _available_seat(db: Session, institute_id: uuid.UUID) -> InstituteSeat | None:
    return db.scalar(
        select(InstituteSeat).where(
            InstituteSeat.institute_id == institute_id,
            InstituteSeat.status == SeatStatus.PURCHASED,
        ).order_by(InstituteSeat.created_at.asc())
    )


def _temp_password() -> str:
    """Random login password that meets auth password rules (never email it back via API JSON)."""
    return secrets.token_urlsafe(14)


def _reject_workspace_account(db: Session, user: User) -> None:
    from backend.app.services.workspace import workspace_for

    ws = workspace_for(db, user)["workspace"]
    if ws == "institute":
        raise AppError(
            "NOT_A_CANDIDATE",
            "That email belongs to an institute account. Invite a student email instead.",
            409,
        )
    if ws == "partner":
        raise AppError(
            "NOT_A_CANDIDATE",
            "That email belongs to a partner account. Invite a student email instead.",
            409,
        )
    if ws == "admin":
        raise AppError("NOT_A_CANDIDATE", "That email belongs to an admin account.", 409)


def _split_student_name(name: str) -> tuple[str, str]:
    name = " ".join(name.split())
    if not name:
        return "", ""
    first, _, last = name.partition(" ")
    return first[:100], last.strip()[:100]


def _apply_student_contact(db: Session, user: User, *, name: str, phone: str, created: bool) -> None:
    from backend.app.models import UserProfile

    first, last = _split_student_name(name)
    phone = phone.strip()[:32]
    if created or not (user.first_name or "").strip():
        user.first_name = first
    if created or not (user.last_name or "").strip():
        user.last_name = last
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    if profile is None:
        db.add(UserProfile(user_id=user.id, phone=phone))
    elif created or not (profile.phone or "").strip():
        profile.phone = phone


def invite_candidate(
    db: Session,
    institute: Institute,
    email: str,
    invited_by: User,
    note: str = "",
    *,
    name: str = "",
    phone: str = "",
) -> tuple[InstituteAssignment, str | None]:
    """Add a student: create account if needed, activate the seat, return temp password if new."""
    require_active(institute)
    email = email.strip().lower()
    name = " ".join((name or "").split())
    phone = (phone or "").strip()
    if not name:
        raise AppError("INVALID_NAME", "Enter the student name.", 422)
    if len(phone) < 5 or len(phone) > 32:
        raise AppError("INVALID_PHONE", "Enter a valid phone number.", 422)
    if "@" not in email or len(email) > 320:
        raise AppError("INVALID_EMAIL", "Enter a valid student email.", 422)
    open_row = db.scalar(select(InstituteAssignment).where(
        InstituteAssignment.institute_id == institute.id,
        InstituteAssignment.candidate_email == email,
        InstituteAssignment.status.in_(OPEN_ASSIGNMENT_STATUSES),
    ))
    if open_row is not None:
        raise AppError("ALREADY_INVITED", "That student already has an open invitation or seat.", 409)
    seat = _available_seat(db, institute.id)
    if seat is None:
        raise AppError("NO_SEATS", "Buy more seats before inviting another student.", 409)

    existing_user = db.scalar(select(User).where(User.email == email))
    temp_password: str | None = None
    created = False
    if existing_user is None:
        created = True
        temp_password = _temp_password()
        first, last = _split_student_name(name)
        existing_user = User(
            email=email,
            password_hash=hash_password(temp_password),
            first_name=first,
            last_name=last,
            is_verified=True,
        )
        db.add(existing_user)
        db.flush()
    else:
        _reject_workspace_account(db, existing_user)

    _apply_student_contact(db, existing_user, name=name, phone=phone, created=created)

    seat.status = SeatStatus.ASSIGNED
    assignment = InstituteAssignment(
        institute_id=institute.id,
        candidate_email=email,
        student_user_id=existing_user.id,
        seat_id=seat.id,
        invited_by_user_id=invited_by.id,
        status=AssignmentStatus.ACTIVE,
        note=note.strip()[:500],
        accepted_at=_now(),
    )
    db.add(assignment)
    db.flush()

    from backend.app.services import partner_service

    partner_service.maybe_accrue_candidate_commission(db, assignment)
    notify_invite_accepted(db, assignment)
    return assignment, temp_password


def managed_institute_for_user(db: Session, user_id: uuid.UUID) -> Institute | None:
    """Sponsoring institute when the user has an active entitled campus seat."""
    assignment = active_assignment_for_user(db, user_id)
    if assignment is None:
        return None
    return db.get(Institute, assignment.institute_id)


def assignment_out(row: InstituteAssignment, db: Session | None = None) -> dict:
    name = ""
    phone = ""
    if db is not None and row.student_user_id:
        from backend.app.models import UserProfile

        student = db.get(User, row.student_user_id)
        if student is not None:
            name = f"{student.first_name} {student.last_name}".strip()
            profile = db.scalar(select(UserProfile).where(UserProfile.user_id == student.id))
            if profile is not None:
                phone = (profile.phone or "").strip()
    return {
        "id": str(row.id),
        "candidate_email": row.candidate_email,
        "candidate_name": name or None,
        "candidate_phone": phone or None,
        "student_user_id": str(row.student_user_id) if row.student_user_id else None,
        "seat_id": str(row.seat_id) if row.seat_id else None,
        "status": row.status.value,
        "note": row.note,
        "accepted_at": _iso(row.accepted_at),
        "released_at": _iso(row.released_at),
        "created_at": _iso(row.created_at),
    }


def assignment_activity_map(db: Session, user_ids: list[uuid.UUID]) -> dict[str, dict]:
    """Per-student searched/applied/skipped/failed totals for a roster page."""
    empty = {"searched": 0, "applied": 0, "skipped": 0, "failed": 0}
    out = {str(uid): dict(empty) for uid in user_ids}
    if not user_ids:
        return out
    for user_id, status, n in db.execute(
        select(Application.user_id, Application.status, func.count())
        .where(Application.user_id.in_(user_ids))
        .group_by(Application.user_id, Application.status)
    ):
        bucket = out.setdefault(str(user_id), dict(empty))
        bucket["searched"] += n
        key = status.value
        if key in ("applied", "skipped", "failed"):
            bucket[key] += n
    return out


def list_assignments(db: Session, institute: Institute, params: PageParams, status: AssignmentStatus | None = None) -> dict:
    stmt = select(InstituteAssignment).where(InstituteAssignment.institute_id == institute.id)
    if status is not None:
        stmt = stmt.where(InstituteAssignment.status == status)
    stmt = stmt.order_by(InstituteAssignment.created_at.desc())
    rows, total = paginate(db, stmt, params)
    activity = assignment_activity_map(db, [r.student_user_id for r in rows if r.student_user_id])
    items = []
    for row in rows:
        payload = assignment_out(row, db)
        payload["activity"] = (
            activity.get(str(row.student_user_id), {"searched": 0, "applied": 0, "skipped": 0, "failed": 0})
            if row.student_user_id else {"searched": 0, "applied": 0, "skipped": 0, "failed": 0}
        )
        items.append(payload)
    return page_response(items, total, params)


def get_assignment(db: Session, institute: Institute, assignment_id: uuid.UUID) -> InstituteAssignment:
    row = db.get(InstituteAssignment, assignment_id)
    if row is None or row.institute_id != institute.id:
        raise AppError("NOT_FOUND", "Student not found.", 404)
    return row


def student_detail(db: Session, institute: Institute, assignment_id: uuid.UUID) -> dict:
    """Assignment, profile, and application totals for one campus student."""
    from backend.app.services.admin_service import _candidate

    row = get_assignment(db, institute, assignment_id)
    user = db.get(User, row.student_user_id) if row.student_user_id else None
    by_status = {s.value: 0 for s in ApplicationStatus}
    candidate = None
    if user is not None:
        for status, count in db.execute(
            select(Application.status, func.count()).where(Application.user_id == user.id).group_by(Application.status)
        ):
            by_status[status.value] = count
        candidate = _candidate(db, user, by_status)
    applied = by_status["applied"]
    failed = by_status["failed"]
    return {
        "assignment": assignment_out(row, db),
        "user": None if user is None else {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "last_login_at": _iso(user.last_login_at),
            "created_at": _iso(user.created_at),
        },
        "activity": {
            "searched": sum(by_status.values()),
            "applied": applied,
            "skipped": by_status["skipped"],
            "failed": failed,
            "success_rate": round(applied / (applied + failed), 4) if applied + failed else None,
        },
        "applications_by_status": by_status,
        "candidate": candidate,
    }


def list_invites(db: Session, institute: Institute) -> list[dict]:
    rows = db.scalars(
        select(InstituteAssignment).where(
            InstituteAssignment.institute_id == institute.id,
            InstituteAssignment.status.in_((AssignmentStatus.INVITED, AssignmentStatus.PENDING_CANDIDATE_ACCEPTANCE)),
        ).order_by(InstituteAssignment.created_at.desc())
    ).all()
    items = []
    for row in rows:
        payload = assignment_out(row, db)
        invite = db.scalar(
            select(InstituteInvite)
            .where(InstituteInvite.assignment_id == row.id, InstituteInvite.accepted_at.is_(None))
            .order_by(InstituteInvite.expires_at.desc())
        )
        payload["expires_at"] = _iso(invite.expires_at) if invite else None
        items.append(payload)
    return items


def list_seats(db: Session, institute: Institute) -> list[dict]:
    rows = db.scalars(
        select(InstituteSeat).where(InstituteSeat.institute_id == institute.id)
        .order_by(InstituteSeat.created_at.asc())
    ).all()
    by_seat: dict[str, InstituteAssignment] = {}
    if rows:
        for assignment in db.scalars(
            select(InstituteAssignment).where(
                InstituteAssignment.institute_id == institute.id,
                InstituteAssignment.seat_id.in_([s.id for s in rows]),
            )
        ):
            if assignment.seat_id is not None:
                by_seat[str(assignment.seat_id)] = assignment
    return [{
        "id": str(s.id),
        "subscription_id": str(s.subscription_id),
        "status": s.status.value,
        "created_at": _iso(s.created_at),
        "assignment": assignment_out(by_seat[str(s.id)], db) if str(s.id) in by_seat else None,
    } for s in rows]


def invite_preview(db: Session, raw_token: str) -> dict:
    invite, assignment = _invite_for(db, raw_token)
    institute = db.get(Institute, assignment.institute_id)
    return {
        "institute_name": institute.name if institute else "Institute",
        "email": assignment.candidate_email,
        "status": assignment.status.value,
        "expires_at": _iso(invite.expires_at),
    }


def _invite_for(db: Session, raw_token: str) -> tuple[InstituteInvite, InstituteAssignment]:
    invite = db.scalar(select(InstituteInvite).where(InstituteInvite.token_hash == hash_token(raw_token)))
    if invite is None or invite.accepted_at is not None or invite.expires_at <= _now():
        raise AppError("INVALID_TOKEN", "This invitation is invalid or has expired.", 400)
    assignment = db.get(InstituteAssignment, invite.assignment_id)
    if assignment is None or assignment.status not in (
        AssignmentStatus.INVITED, AssignmentStatus.PENDING_CANDIDATE_ACCEPTANCE,
    ):
        raise AppError("INVALID_TOKEN", "This invitation is no longer open.", 400)
    return invite, assignment


def accept_invite(db: Session, user: User, raw_token: str) -> InstituteAssignment:
    invite, assignment = _invite_for(db, raw_token)
    if user.email != assignment.candidate_email:
        raise AppError("INVITE_EMAIL_MISMATCH", "Log in with the email this invitation was sent to.", 403)
    assignment.student_user_id = user.id
    assignment.status = AssignmentStatus.ACTIVE
    assignment.accepted_at = _now()
    invite.accepted_at = _now()
    if assignment.seat_id:
        seat = db.get(InstituteSeat, assignment.seat_id)
        if seat is not None:
            seat.status = SeatStatus.ASSIGNED
    db.flush()
    from backend.app.services import partner_service

    partner_service.maybe_accrue_candidate_commission(db, assignment)
    notify_invite_accepted(db, assignment)
    return assignment


def notify_candidate_invited(db: Session, institute: Institute, candidate_email: str, raw_token: str) -> None:
    from backend.app.models import User
    from backend.app.services import notification_service

    user = db.scalar(select(User).where(User.email == candidate_email.lower().strip()))
    if user is None:
        return
    link = f"/invite/{raw_token}"
    notification_service.notify_event(
        db,
        user.id,
        "institute_invite",
        link=link,
        variables={
            "institute_name": institute.name,
            "message": f"{institute.name} reserved a seat for you. Open the invitation to accept.",
        },
    )


def notify_invite_accepted(db: Session, assignment: InstituteAssignment) -> None:
    from backend.app.models.enums import InstituteMemberRole
    from backend.app.services import notification_service

    institute = db.get(Institute, assignment.institute_id)
    if institute is None:
        return
    admins = db.scalars(
        select(InstituteMember).where(
            InstituteMember.institute_id == institute.id,
            InstituteMember.role == InstituteMemberRole.ADMIN,
        )
    ).all()
    message = f"{assignment.candidate_email} joined {institute.name}."
    for member in admins:
        notification_service.notify_event(
            db,
            member.user_id,
            "institute_invite_accepted",
            link="/institute/students",
            variables={"candidate_email": assignment.candidate_email, "institute_name": institute.name, "message": message},
        )


_RELEASABLE_STATUSES = (*OPEN_ASSIGNMENT_STATUSES, AssignmentStatus.SUSPENDED)


def release_assignment(
    db: Session, institute: Institute, assignment_id: uuid.UUID,
) -> tuple[InstituteAssignment, str | None]:
    """Unbind a candidate from campus billing. Institute seats stay in inventory as available."""
    assignment = db.get(InstituteAssignment, assignment_id)
    if assignment is None or assignment.institute_id != institute.id:
        raise AppError("NOT_FOUND", "Assignment not found.", 404)
    if assignment.status not in _RELEASABLE_STATUSES:
        raise AppError("NOT_OPEN", "That candidate is already released from this campus.", 409)
    notify_email = (
        assignment.candidate_email
        if assignment.status in (AssignmentStatus.ACTIVE, AssignmentStatus.SUSPENDED)
        else None
    )
    _free_seat(db, assignment)
    assignment.status = AssignmentStatus.RELEASED
    assignment.released_at = _now()
    db.flush()
    return assignment, notify_email


def suspend_assignment(
    db: Session, institute: Institute, assignment_id: uuid.UUID,
) -> tuple[InstituteAssignment, str | None]:
    """Suspend an active student. Returns (assignment, student_email_to_notify)."""
    assignment = db.get(InstituteAssignment, assignment_id)
    if assignment is None or assignment.institute_id != institute.id:
        raise AppError("NOT_FOUND", "Assignment not found.", 404)
    if assignment.status != AssignmentStatus.ACTIVE:
        raise AppError("NOT_ACTIVE", "Only an active student can be suspended.", 409)
    notify_email = assignment.candidate_email
    _free_seat(db, assignment)
    assignment.status = AssignmentStatus.SUSPENDED
    assignment.released_at = _now()
    db.flush()
    return assignment, notify_email


def _free_seat(db: Session, assignment: InstituteAssignment) -> None:
    if assignment.seat_id is None:
        return
    seat = db.get(InstituteSeat, assignment.seat_id)
    if seat is not None and seat.status == SeatStatus.ASSIGNED:
        seat.status = SeatStatus.PURCHASED
    assignment.seat_id = None


def close_assignments(db: Session, institute: Institute, status: AssignmentStatus = AssignmentStatus.SUSPENDED) -> int:
    rows = db.scalars(select(InstituteAssignment).where(
        InstituteAssignment.institute_id == institute.id,
        InstituteAssignment.status.in_(OPEN_ASSIGNMENT_STATUSES),
    )).all()
    for row in rows:
        _free_seat(db, row)
        row.status = status
        row.released_at = _now()
    db.flush()
    return len(rows)


def set_status(db: Session, institute: Institute, status: InstituteStatus) -> Institute:
    if status not in InstituteStatus:
        raise AppError("INVALID_STATUS", "Unknown institute status.", 422)
    institute.status = status
    if status in (InstituteStatus.SUSPENDED, InstituteStatus.CLOSED):
        close_assignments(db, institute, AssignmentStatus.SUSPENDED if status == InstituteStatus.SUSPENDED else AssignmentStatus.CANCELLED)
    db.flush()
    return institute


def update_by_admin(db: Session, institute: Institute, *, name: str, contact_name: str = "", phone: str = "") -> Institute:
    save_profile(db, institute, {"name": name, "contact_name": contact_name, "phone": phone})
    return institute


def save_profile(db: Session, institute: Institute, body: dict) -> Institute:
    if name := (body.get("name") or "").strip():
        institute.name = name[:190]
    if contact := (body.get("contact_name") or "").strip():
        institute.contact_name = contact[:190]
    if "phone" in body:
        institute.phone = str(body.get("phone") or "")[:32]
    itype = str(body.get("institute_type") or institute.institute_type).upper()
    institute.institute_type = itype if itype in INSTITUTE_TYPES else institute.institute_type
    gstin, pan = _validate_tax(body.get("gstin") or "", body.get("pan_number") or "")
    if "gstin" in body:
        institute.gstin = gstin
    if "pan_number" in body:
        institute.pan_number = pan
    db.flush()
    return institute


def save_settings(db: Session, institute: Institute, body: dict) -> Institute:
    current = {**DEFAULT_SETTINGS, **(institute.settings or {})}
    if "timezone" in body and body["timezone"]:
        current["timezone"] = str(body["timezone"])[:64]
    for key in ("notify_invites", "notify_acceptances", "notify_low_seats"):
        if key in body:
            current[key] = bool(body[key])
    if "low_seat_threshold" in body:
        current["low_seat_threshold"] = max(1, min(50, int(body["low_seat_threshold"])))
    if "invite_expiry_days" in body:
        current["invite_expiry_days"] = max(1, min(30, int(body["invite_expiry_days"])))
    if "invite_note" in body:
        current["invite_note"] = str(body["invite_note"] or "")[:500]
    institute.settings = current
    db.flush()
    return institute


def reports(db: Session, institute: Institute) -> dict:
    by_status = {s.value: 0 for s in AssignmentStatus}
    for status, n in db.execute(
        select(InstituteAssignment.status, func.count()).where(InstituteAssignment.institute_id == institute.id)
        .group_by(InstituteAssignment.status)
    ):
        by_status[status.value if hasattr(status, "value") else status] = n
    return {"seats": seat_counts(db, institute.id), "assignments_by_status": by_status}


def grant_plan(db: Session, institute: Institute, plan_code: str, months: int) -> Subscription:
    plan = billing_service.get_plan(db, plan_code)
    if getattr(plan, "kind", PlanKind.PERSONAL) != PlanKind.INSTITUTE and PLAN_LIMITS.get(plan.code, {}).get("kind") != "institute":
        raise AppError("NOT_INSTITUTE_PLAN", "Choose a campus seat plan.", 422)
    now = _now()
    for old in db.scalars(select(Subscription).where(
        Subscription.institute_id == institute.id,
        Subscription.status.in_(billing_service.ENTITLED),
    )).all():
        old.status, old.current_period_end = SubscriptionStatus.CANCELLED, now
    admin_user_id = institute.claimed_by_user_id
    if admin_user_id is None:
        member = db.scalar(select(InstituteMember).where(InstituteMember.institute_id == institute.id)
                           .order_by(InstituteMember.created_at.asc()))
        admin_user_id = member.user_id if member else None
    if admin_user_id is None:
        raise AppError("NO_ADMIN", "This institute has no admin user.", 400)
    sub = Subscription(
        user_id=admin_user_id,
        institute_id=institute.id,
        plan_id=plan.id,
        plan=plan,
        status=SubscriptionStatus.ACTIVE,
        provider="admin",
        current_period_start=now,
        current_period_end=now + timedelta(days=30 * months),
        cancel_at_period_end=True,
    )
    db.add(sub)
    db.flush()
    ensure_seats_for_subscription(db, sub)
    return sub


def list_institutes(db: Session, params: PageParams, q: str | None = None, status: InstituteStatus | None = None) -> dict:
    stmt = select(Institute).order_by(Institute.created_at.desc())
    if status is not None:
        stmt = stmt.where(Institute.status == status)
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(Institute.name).like(like), func.lower(Institute.email).like(like)))
    rows, total = paginate(db, stmt, params)
    return page_response([institute_out(db, r) for r in rows], total, params)


def get_institute(db: Session, institute_id: uuid.UUID) -> Institute:
    institute = db.get(Institute, institute_id)
    if institute is None:
        raise AppError("NOT_FOUND", "Institute not found.", 404)
    return institute


def admin_user(db: Session, institute: Institute) -> User | None:
    if institute.claimed_by_user_id:
        return db.get(User, institute.claimed_by_user_id)
    member = db.scalar(select(InstituteMember).where(
        InstituteMember.institute_id == institute.id, InstituteMember.role == InstituteMemberRole.ADMIN,
    ).order_by(InstituteMember.created_at.asc()))
    return db.get(User, member.user_id) if member else None


def active_assignment_for_user(db: Session, user_id: uuid.UUID) -> InstituteAssignment | None:
    now = _now()
    return db.scalar(
        select(InstituteAssignment)
        .join(InstituteSeat, InstituteSeat.id == InstituteAssignment.seat_id)
        .join(Subscription, Subscription.id == InstituteSeat.subscription_id)
        .where(
            InstituteAssignment.student_user_id == user_id,
            InstituteAssignment.status == AssignmentStatus.ACTIVE,
            InstituteSeat.status == SeatStatus.ASSIGNED,
            Subscription.status.in_(billing_service.ENTITLED),
            or_(Subscription.current_period_end.is_(None), Subscription.current_period_end > now),
        )
        .order_by(InstituteAssignment.accepted_at.desc())
    )
