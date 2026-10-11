"""
Admin-only reads across all users, and the few changes an admin can make. Every change is
recorded in `admin_actions`. Admins never see resume files, application answers, or anything
the payment provider holds (cards, UPI IDs).
"""

import logging
import uuid
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.errors import AppError
from backend.app.core.pagination import PageParams, paginate, page_response
from backend.app.core.plans import FREE_PLAN, PLAN_LIMITS
from backend.app.core.security import hash_password
from backend.app.models import (
    AdminAction, AgentDevice, Application, ApplicationPreferences, ApplicationStatus, AuthToken, AutomationJob,
    AutomationLog, AutomationStatus, Job, TokenPurpose,
    LiveInterviewOrder, LiveInterviewSession, LiveInterviewToken, MockInterviewFeedbackJob, MockInterviewSession,
    Payment, Plan, Resume, SearchConfig, Subscription, SubscriptionStatus, User, UserProfile, UsageCounter,
)
from backend.app.models.enums import ACTIVE_AUTOMATION_STATUSES, MockInterviewSessionStatus, PlanKind
from backend.app.services.mock_interview_feedback_jobs import JOB_FAILED
from backend.app.services import (
    agent_service, auth_service, automation_service, billing_service, dashboard_service, email_service,
    live_interview_service, notification_service, usage_service,
)
from backend.app.services.payments.base import PaymentProvider

logger = logging.getLogger("applyxai.admin")

ADMIN_PROVIDER = "admin"
MAX_GRANT_MONTHS = 24
MIN_PAID_PRICE = 100          # Razorpay's minimum charge is 1.00 in the currency's main unit


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()


def _like(term: str) -> str:
    return "%" + term.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _audit(db: Session, admin: User, action: str, target: User | None = None, target_label: str = "",
           **details) -> None:
    db.add(AdminAction(admin_id=admin.id, admin_email=admin.email, action=action,
                       target_user_id=target.id if target else None,
                       target=(target.email if target else target_label)[:320], details=details))
    db.flush()


def _entitled_filter(now: datetime):
    return (Subscription.status.in_(billing_service.ENTITLED),
            or_(Subscription.current_period_end.is_(None), Subscription.current_period_end > now))


def _get_user(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise AppError("NOT_FOUND", "User not found", 404)
    return user


# ----------------------------------------------------------------------------- analytics
def analytics(db: Session, now: datetime | None = None) -> dict:
    now = now or _now()
    count = lambda *where: db.scalar(select(func.count()).select_from(User).where(*where))  # noqa: E731
    users = {
        "total": count(), "active": count(User.is_active.is_(True)), "verified": count(User.is_verified.is_(True)),
        "admins": count(User.is_admin.is_(True)),
        "new_7d": count(User.created_at >= now - timedelta(days=7)),
        "new_30d": count(User.created_at >= now - timedelta(days=30)),
        "active_30d": count(User.last_login_at >= now - timedelta(days=30)),
    }

    entitled = _entitled_filter(now)
    subs_with_plan = lambda *cols: select(*cols).select_from(Subscription).join(Plan, Plan.id == Subscription.plan_id)  # noqa: E731
    by_plan = db.execute(subs_with_plan(Plan.code, Plan.name, func.count(Subscription.id)).where(*entitled)
                         .group_by(Plan.code, Plan.name).order_by(Plan.code)).all()
    mrr: dict[str, int] = {}
    for currency, total in db.execute(subs_with_plan(Plan.currency, func.sum(Plan.price_cents))
                                      .where(*entitled, Subscription.provider != ADMIN_PROVIDER,
                                             Subscription.cancel_at_period_end.is_(False))
                                      .group_by(Plan.currency)):
        mrr[currency] = int(total or 0)
    revenue: dict[str, int] = {}
    for currency, total in db.execute(select(Payment.currency, func.sum(Payment.amount_cents))
                                      .where(Payment.status == "captured",
                                             Payment.created_at >= now - timedelta(days=30))
                                      .group_by(Payment.currency)):
        revenue[currency] = int(total or 0)
    past_due = db.scalar(select(func.count()).select_from(Subscription)
                         .where(Subscription.status == SubscriptionStatus.PAST_DUE))

    period_start, _ = usage_service.period_bounds(usage_service.current_period(now))
    by_status = {s.value: 0 for s in ApplicationStatus}
    for status, n in db.execute(select(Application.status, func.count())
                                .where(Application.updated_at >= period_start).group_by(Application.status)):
        by_status[status.value] = n
    today = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    chart_start = today - timedelta(days=dashboard_service.CHART_DAYS - 1)
    daily = dashboard_service.daily_series(db, chart_start)

    runs_by_status = {s.value: 0 for s in AutomationStatus}
    for status, n in db.execute(select(AutomationJob.status, func.count())
                                .where(AutomationJob.created_at >= now - timedelta(hours=24))
                                .group_by(AutomationJob.status)):
        runs_by_status[status.value] = n
    active_runs = db.scalar(select(func.count()).select_from(AutomationJob)
                            .where(AutomationJob.status.in_(ACTIVE_AUTOMATION_STATUSES)))
    devices = db.scalars(select(AgentDevice).where(AgentDevice.token_hash.is_not(None),
                                                   AgentDevice.revoked_at.is_(None))).all()

    mi_by_status = {s.value: 0 for s in MockInterviewSessionStatus}
    for status, n in db.execute(
        select(MockInterviewSession.status, func.count()).group_by(MockInterviewSession.status)
    ):
        mi_by_status[status.value] = n
    mi_this_month = db.scalar(
        select(func.count())
        .select_from(MockInterviewSession)
        .where(MockInterviewSession.created_at >= period_start)
    ) or 0
    mi_failed_jobs_24h = db.scalar(
        select(func.count())
        .select_from(MockInterviewFeedbackJob)
        .where(
            MockInterviewFeedbackJob.status == JOB_FAILED,
            MockInterviewFeedbackJob.created_at >= now - timedelta(hours=24),
        )
    ) or 0

    return {
        "users": users,
        "subscriptions": {"by_plan": [{"code": c, "name": n, "count": k} for c, n, k in by_plan],
                          "mrr_cents": mrr, "past_due": past_due},
        "revenue_30d_cents": revenue,
        "applications": {"this_month_by_status": by_status, "daily": [{"date": d, **v} for d, v in daily.items()]},
        "automation": {"active_runs": active_runs, "last_24h_by_status": runs_by_status,
                       "devices": len(devices), "devices_online": sum(agent_service.is_online(d, now) for d in devices)},
        "mock_interviews": {
            "total_sessions": sum(mi_by_status.values()),
            "this_month": mi_this_month,
            "by_status": mi_by_status,
            "failed_feedback_jobs_24h": mi_failed_jobs_24h,
        },
    }


# ----------------------------------------------------------------------------- users
def _user_row(db: Session, user: User, applications: int) -> dict:
    limits = usage_service.plan_limits(db, user.id)
    return {
        "id": str(user.id), "email": user.email, "first_name": user.first_name, "last_name": user.last_name,
        "is_active": user.is_active, "is_verified": user.is_verified, "is_admin": user.is_admin,
        "created_at": _iso(user.created_at), "last_login_at": _iso(user.last_login_at),
        "plan": limits["plan"], "plan_name": limits["name"], "applications_this_month": applications,
    }


def list_users(db: Session, params: PageParams, *, q: str | None = None, status: str | None = None,
               plan: str | None = None) -> dict:
    stmt = select(User).order_by(User.created_at.desc(), User.id)
    if q and q.strip():
        term = _like(q)
        stmt = stmt.where(or_(func.lower(User.email).like(term, escape="\\"),
                              func.lower(User.first_name + " " + User.last_name).like(term, escape="\\")))
    if status == "active":
        stmt = stmt.where(User.is_active.is_(True))
    elif status == "disabled":
        stmt = stmt.where(User.is_active.is_(False))
    elif status == "admin":
        stmt = stmt.where(User.is_admin.is_(True))
    elif status == "unverified":
        stmt = stmt.where(User.is_verified.is_(False))
    if plan:
        paying = select(Subscription.user_id).join(Subscription.plan).where(*_entitled_filter(_now()))
        if plan == FREE_PLAN:
            stmt = stmt.where(User.id.not_in(paying))
        else:
            stmt = stmt.where(User.id.in_(paying.where(Plan.code == plan)))
    users, total = paginate(db, stmt, params)
    period = usage_service.current_period()
    used = dict(db.execute(select(UsageCounter.user_id, UsageCounter.applications)
                           .where(UsageCounter.period == period, UsageCounter.user_id.in_([u.id for u in users]))).all())
    return page_response([_user_row(db, u, used.get(u.id, 0)) for u in users], total, params)


def user_detail(db: Session, user_id: uuid.UUID) -> dict:
    user = _get_user(db, user_id)
    usage = usage_service.usage_summary(db, user.id)
    subs = db.scalars(select(Subscription).where(Subscription.user_id == user.id)
                      .order_by(Subscription.created_at.desc()).limit(20)).all()
    runs = db.scalars(select(AutomationJob).where(AutomationJob.user_id == user.id)
                      .order_by(AutomationJob.created_at.desc()).limit(10)).all()
    devices = db.scalars(select(AgentDevice).where(AgentDevice.user_id == user.id, AgentDevice.token_hash.is_not(None),
                                                   AgentDevice.revoked_at.is_(None))).all()
    payments = db.scalars(select(Payment).where(Payment.user_id == user.id)
                          .order_by(Payment.created_at.desc()).limit(20)).all()
    by_status = {s.value: 0 for s in ApplicationStatus}
    for status, n in db.execute(select(Application.status, func.count()).where(Application.user_id == user.id)
                                .group_by(Application.status)):
        by_status[status.value] = n
    resumes = db.scalar(select(func.count()).select_from(Resume).where(Resume.user_id == user.id))
    return {
        "user": _user_row(db, user, usage["applications"]["used"]),
        "usage": usage,
        "subscription": billing_service.sub_out(billing_service.current_subscription(db, user.id)),
        "subscriptions": [billing_service.sub_out(s) for s in subs],
        "payments": [billing_service.payment_out(p) for p in payments],
        "runs": [automation_service.run_out(r) for r in runs],
        "devices": [agent_service.device_out(d) for d in devices],
        "applications_by_status": by_status,
        "resumes": resumes,
        "candidate": _candidate(db, user, by_status),
    }


def _candidate(db: Session, user: User, by_status: dict[str, int]) -> dict:
    """Profile, search, resumes (names only), recent applications, and interviews for one candidate."""
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    search = db.scalar(select(SearchConfig).where(SearchConfig.user_id == user.id))
    resumes = db.scalars(select(Resume).where(Resume.user_id == user.id)
                         .order_by(Resume.is_default.desc(), Resume.created_at.desc()).limit(50)).all()
    recent = db.execute(
        select(Application, Job).join(Job, Job.id == Application.job_id)
        .where(Application.user_id == user.id)
        .order_by(func.coalesce(Application.applied_at, Application.created_at).desc()).limit(25)
    ).all()
    since = _now() - timedelta(days=29)
    daily: dict[str, dict[str, int]] = {}
    for applied_at, status in db.execute(
        select(func.coalesce(Application.applied_at, Application.created_at), Application.status)
        .where(Application.user_id == user.id,
               func.coalesce(Application.applied_at, Application.created_at) >= since,
               Application.status.in_([ApplicationStatus.APPLIED, ApplicationStatus.FAILED]))
    ):
        day = applied_at.date().isoformat()
        bucket = daily.setdefault(day, {"applied": 0, "failed": 0})
        bucket["applied" if status == ApplicationStatus.APPLIED else "failed"] += 1
    days = [(since + timedelta(days=i)).date().isoformat() for i in range(30)]

    mocks = db.scalars(select(MockInterviewSession).where(MockInterviewSession.user_id == user.id)
                       .order_by(MockInterviewSession.created_at.desc()).limit(25)).all()
    mock_total = db.scalar(select(func.count()).select_from(MockInterviewSession)
                           .where(MockInterviewSession.user_id == user.id)) or 0
    lives = db.execute(
        select(LiveInterviewSession, LiveInterviewToken)
        .join(LiveInterviewToken, LiveInterviewToken.id == LiveInterviewSession.token_id)
        .where(LiveInterviewSession.user_id == user.id)
        .order_by(LiveInterviewSession.created_at.desc()).limit(50)
    ).all()
    tokens = {status: n for status, n in db.execute(
        select(LiveInterviewToken.status, func.count()).where(LiveInterviewToken.user_id == user.id)
        .group_by(LiveInterviewToken.status))}
    paid = db.execute(
        select(LiveInterviewOrder.currency, func.coalesce(func.sum(LiveInterviewOrder.amount_cents), 0))
        .where(LiveInterviewOrder.user_id == user.id, LiveInterviewOrder.status == "paid")
        .group_by(LiveInterviewOrder.currency)
    ).all()

    applied = by_status.get(ApplicationStatus.APPLIED.value, 0)
    failed = by_status.get(ApplicationStatus.FAILED.value, 0)
    mock_scores = [_score(m.feedback) for m in mocks]
    live_scores = [_score(s.feedback) for s, _ in lives]
    return {
        "profile": {
            "phone": profile.phone if profile else "",
            "headline": profile.headline if profile else "",
            "summary": profile.summary if profile else "",
            "current_title": profile.current_title if profile else "",
            "current_company": profile.current_company if profile else "",
            "experience_years": profile.experience_years if profile else None,
            "skills": list(profile.skills or []) if profile else [],
            "preferred_roles": list(profile.preferred_roles or []) if profile else [],
            "preferred_locations": list(profile.preferred_locations or []) if profile else [],
            "education": list(profile.education or []) if profile else [],
            "work_history": list(profile.work_history or []) if profile else [],
        },
        "search": None if search is None else {
            "keywords": list(search.keywords or []),
            "location": search.location,
            "easy_apply_only": search.easy_apply_only,
            "experience_level": list(search.experience_level or []),
            "job_type": list(search.job_type or []),
            "on_site": list(search.on_site or []),
            "date_posted": search.date_posted,
            "salary_min": search.salary_min,
            "salary_max": search.salary_max,
        },
        "resume_list": [{
            "id": str(r.id), "name": r.name, "file_type": r.file_type, "file_size": r.file_size,
            "is_default": r.is_default, "tailored": r.application_id is not None, "created_at": _iso(r.created_at),
        } for r in resumes],
        "stats": {
            "applications_total": sum(by_status.values()),
            "applied_total": applied,
            "success_rate": round(applied * 100 / (applied + failed)) if applied + failed else None,
            "mock_interviews_total": mock_total,
            "mock_average_score": _average(mock_scores),
            "live_interviews_total": len(lives),
            "live_average_score": _average(live_scores),
        },
        "applications_daily": [{"date": d, **daily.get(d, {"applied": 0, "failed": 0})} for d in days],
        "recent_applications": [{
            "id": str(app.id), "status": app.status.value, "title": job.title, "company": job.company,
            "location": job.location, "job_url": job.job_url, "failure_reason": app.failure_reason,
            "applied_at": _iso(app.applied_at), "created_at": _iso(app.created_at),
        } for app, job in recent],
        "mock_interviews": [{
            "id": str(m.id), "status": m.status.value,
            "job_title": str((m.context_snapshot or {}).get("job_title") or ""),
            "company": str((m.context_snapshot or {}).get("company") or ""),
            "interview_types": list(m.interview_types or []), "turn_count": m.turn_count,
            "overall_score": score, "created_at": _iso(m.created_at),
        } for m, score in zip(mocks, mock_scores)],
        "live_interviews": [{
            "id": str(s.id), "status": s.status, "job_title": s.job_title, "company": s.company,
            "token": t.code, "token_status": t.status, "overall_score": score,
            "lines": len(s.transcript or []), "started_at": _iso(s.started_at), "ended_at": _iso(s.ended_at),
        } for (s, t), score in zip(lives, live_scores)],
        "live_tokens": {
            "unused": tokens.get("unused", 0), "reserved": tokens.get("reserved", 0), "used": tokens.get("used", 0),
            "paid": [{"currency": c, "amount_cents": int(a)} for c, a in paid],
        },
        "journey": _journey(db, user, profile, search),
    }


def _journey(db: Session, user: User, profile: UserProfile | None, search: SearchConfig | None) -> dict:
    """Each setup step after registration with when it happened, and the first step still open."""
    def first(column, *where):
        return db.scalar(select(func.min(column)).where(*where))

    uid = user.id
    verified_at = first(AuthToken.used_at, AuthToken.user_id == uid, AuthToken.purpose == TokenPurpose.VERIFY_EMAIL) \
        if user.is_verified else None
    signed_in_at = first(AuthToken.created_at, AuthToken.user_id == uid, AuthToken.purpose == TokenPurpose.REFRESH) \
        or user.last_login_at
    profile_filled = profile is not None and bool(
        profile.headline or profile.summary or profile.skills or profile.work_history or profile.current_title)
    answers = db.scalar(select(ApplicationPreferences).where(ApplicationPreferences.user_id == uid))
    steps = [
        ("registered", "Registered", True, user.created_at, False),
        ("email_verified", "Verified email", user.is_verified, verified_at, False),
        ("signed_in", "First sign-in", signed_in_at is not None, signed_in_at, False),
        ("resume", "Uploaded a resume", None, first(Resume.created_at, Resume.user_id == uid), False),
        ("profile", "Filled in profile", profile_filled, profile.updated_at if profile_filled else None, False),
        ("job_preferences", "Saved job preferences", search is not None, search.created_at if search else None, False),
        ("application_answers", "Saved application answers", answers is not None,
         answers.created_at if answers else None, True),
        ("desktop_agent", "Connected the desktop agent", None, first(AgentDevice.paired_at, AgentDevice.user_id == uid), False),
        ("first_run", "Started automation", None, first(AutomationJob.created_at, AutomationJob.user_id == uid), False),
        ("first_application", "First job applied", None,
         first(Application.applied_at, Application.user_id == uid, Application.status == ApplicationStatus.APPLIED), False),
    ]
    out = [{"key": key, "label": label, "done": bool(at) if done is None else done, "at": _iso(at), "optional": optional}
           for key, label, done, at, optional in steps]
    stopped = next((s for s in out if not s["done"] and not s["optional"]), None)
    actions = {
        "email_verified": "Verify email", "signed_in": "Sign in for the first time", "resume": "Upload a resume",
        "profile": "Fill in profile", "job_preferences": "Save job preferences",
        "desktop_agent": "Connect the desktop agent", "first_run": "Start automation", "first_application": "Apply to a first job",
    }
    latest = [t for t in (
        user.last_login_at,
        db.scalar(select(func.max(Application.updated_at)).where(Application.user_id == uid)),
        db.scalar(select(func.max(AutomationJob.updated_at)).where(AutomationJob.user_id == uid)),
        db.scalar(select(func.max(AgentDevice.last_seen_at)).where(AgentDevice.user_id == uid)),
        db.scalar(select(func.max(Resume.created_at)).where(Resume.user_id == uid)),
        db.scalar(select(func.max(MockInterviewSession.updated_at)).where(MockInterviewSession.user_id == uid)),
        db.scalar(select(func.max(LiveInterviewSession.updated_at)).where(LiveInterviewSession.user_id == uid)),
        profile.updated_at if profile else None,
        search.updated_at if search else None,
        *(at for _, _, _, at, _ in steps),
    ) if t]
    last = max((t if t.tzinfo else t.replace(tzinfo=timezone.utc) for t in latest), default=None)
    return {
        "steps": out,
        "stopped_at": stopped["key"] if stopped else None,
        "stopped_label": actions.get(stopped["key"], stopped["label"]) if stopped else None,
        "stopped_step": out.index(stopped) + 1 if stopped else None,
        "completed": sum(1 for s in out if s["done"]),
        "total": len(out),
        "last_activity_at": _iso(last),
    }


def _score(feedback) -> int | None:
    value = feedback.get("overall_score") if isinstance(feedback, dict) else None
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _average(scores: list[int | None]) -> int | None:
    known = [s for s in scores if s is not None]
    return round(sum(known) / len(known)) if known else None


def user_live_interview(db: Session, user_id: uuid.UUID, session_id: uuid.UUID) -> dict:
    user = _get_user(db, user_id)
    return {"user": {"id": str(user.id), "email": user.email, "name": f"{user.first_name} {user.last_name}".strip()},
            "session": live_interview_service.get_session(db, user.id, session_id)}


def create_user(
    db: Session,
    admin: User,
    *,
    email: str,
    password: str,
    first_name: str = "",
    last_name: str = "",
    is_admin: bool = False,
    is_verified: bool = True,
) -> dict:
    email = auth_service.normalize_email(email)
    if password.lower() == email:
        raise AppError("WEAK_PASSWORD", "Password must not be the email address.", 422)
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise AppError("EMAIL_TAKEN", "That email already has an account.", 409)
    user = User(
        email=email,
        password_hash=hash_password(password),
        first_name=first_name[:100],
        last_name=last_name[:100],
        is_admin=is_admin,
        is_verified=is_verified,
        is_active=True,
    )
    db.add(user)
    db.flush()
    _audit(db, admin, "user.create", user, is_admin=is_admin, is_verified=is_verified)
    db.flush()
    return user_detail(db, user.id)


def update_user(
    db: Session,
    admin: User,
    user_id: uuid.UUID,
    *,
    email: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    is_active: bool | None = None,
    is_admin: bool | None = None,
    is_verified: bool | None = None,
) -> dict:
    user = _get_user(db, user_id)
    if user.id == admin.id and (is_active is False or is_admin is False):
        raise AppError("CANNOT_CHANGE_SELF", "You can't disable your own account or remove your own admin access.", 400)
    changes = {}
    if email is not None:
        email_norm = auth_service.normalize_email(email)
        if email_norm != user.email:
            if db.scalar(select(User.id).where(User.email == email_norm, User.id != user.id)) is not None:
                raise AppError("EMAIL_TAKEN", "That email already has an account.", 409)
            changes["email"] = [user.email, email_norm]
            user.email = email_norm
    if first_name is not None and first_name != user.first_name:
        changes["first_name"] = [user.first_name, first_name]
        user.first_name = first_name[:100]
    if last_name is not None and last_name != user.last_name:
        changes["last_name"] = [user.last_name, last_name]
        user.last_name = last_name[:100]
    if is_verified is not None and is_verified != user.is_verified:
        changes["is_verified"] = [user.is_verified, is_verified]
        user.is_verified = is_verified
    if is_admin is not None and is_admin != user.is_admin:
        changes["is_admin"] = [user.is_admin, is_admin]
        user.is_admin = is_admin
    if is_active is not None and is_active != user.is_active:
        changes["is_active"] = [user.is_active, is_active]
        user.is_active = is_active
        if not is_active:
            auth_service.revoke_all_sessions(db, user.id)        # also disconnects their computers
            active = automation_service.active_run(db, user.id)
            if active is not None and active.control != automation_service.CONTROL_STOP:
                automation_service.stop_run(db, user.id, active.id, reason=automation_service.STOP_ADMIN)
    if changes:
        _audit(db, admin, "user.update", user, **changes)
    db.flush()
    return user_detail(db, user.id)


def set_user_password(db: Session, admin: User, user_id: uuid.UUID, password: str) -> dict:
    user = _get_user(db, user_id)
    email = user.email
    if password.lower() == email:
        raise AppError("WEAK_PASSWORD", "Password must not be the email address.", 422)
    user.password_hash = hash_password(password)
    auth_service.revoke_all_sessions(db, user.id)
    _audit(db, admin, "user.password", user)
    db.flush()
    return user_detail(db, user.id)


def delete_user(db: Session, admin: User, user_id: uuid.UUID) -> None:
    user = _get_user(db, user_id)
    if user.id == admin.id:
        raise AppError("CANNOT_DELETE_SELF", "You can't delete your own account.", 400)
    if user.is_admin:
        admins = db.scalar(select(func.count()).select_from(User).where(User.is_admin.is_(True))) or 0
        if admins <= 1:
            raise AppError("LAST_ADMIN", "At least one admin account must remain.", 400)
    _audit(db, admin, "user.delete", user)
    db.delete(user)
    db.flush()


def grant_plan(db: Session, admin: User, user_id: uuid.UUID, plan_code: str, months: int, note: str = "") -> dict:
    """A complimentary plan, with no payment. Replaces an earlier grant; refused while the user pays."""
    user = _get_user(db, user_id)
    plan = billing_service.get_plan(db, plan_code)
    if plan.code == FREE_PLAN:
        raise AppError("FREE_PLAN", "Everyone has the Free plan already. Revoke the grant instead.", 400)
    if not 1 <= months <= MAX_GRANT_MONTHS:
        raise AppError("INVALID_MONTHS", f"Choose between 1 and {MAX_GRANT_MONTHS} months.", 422)
    current = billing_service.current_subscription(db, user.id)
    if current is not None and current.provider != ADMIN_PROVIDER:
        raise AppError("HAS_SUBSCRIPTION", "This user pays for a plan. Their paid plan has to end first.", 409)
    now = _now()
    for old in db.scalars(select(Subscription).where(Subscription.user_id == user.id,
                                                     Subscription.provider == ADMIN_PROVIDER,
                                                     Subscription.status.in_(billing_service.ENTITLED))).all():
        old.status, old.current_period_end = SubscriptionStatus.CANCELLED, now
    end = now + timedelta(days=30 * months)
    db.add(Subscription(user_id=user.id, plan_id=plan.id, status=SubscriptionStatus.ACTIVE, provider=ADMIN_PROVIDER,
                        current_period_start=now, current_period_end=end, cancel_at_period_end=True))
    until = end.strftime("%d %b %Y")
    notification_service.notify_event(
        db, user.id, "plan_granted", link="/billing",
        variables={"plan_name": plan.name, "message": f"It's on us until {until}. No payment is needed."},
    )
    _audit(db, admin, "plan.grant", user, plan=plan.code, months=months, until=end.isoformat(), note=note[:500])
    db.flush()
    return user_detail(db, user.id)


def revoke_grant(db: Session, admin: User, user_id: uuid.UUID) -> dict:
    user = _get_user(db, user_id)
    grants = db.scalars(select(Subscription).where(Subscription.user_id == user.id,
                                                   Subscription.provider == ADMIN_PROVIDER,
                                                   Subscription.status.in_(billing_service.ENTITLED))).all()
    if not grants:
        raise AppError("NO_GRANT", "This user has no complimentary plan.", 404)
    now = _now()
    for sub in grants:
        sub.status, sub.current_period_end = SubscriptionStatus.CANCELLED, now
    _audit(db, admin, "plan.revoke", user, plans=[s.plan.code for s in grants])
    db.flush()
    return user_detail(db, user.id)


# ----------------------------------------------------------------------------- lists
def list_subscriptions(db: Session, params: PageParams, *, status: str | None = None, plan: str | None = None) -> dict:
    stmt = (select(Subscription, User.email).join(User, User.id == Subscription.user_id).join(Subscription.plan)
            .order_by(Subscription.created_at.desc(), Subscription.id))
    if status:
        stmt = stmt.where(Subscription.status == SubscriptionStatus(status))
    if plan:
        stmt = stmt.where(Plan.code == plan)
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.execute(stmt.limit(params.page_size).offset((params.page - 1) * params.page_size)).all()
    items = [{**billing_service.sub_out(s), "user_id": str(s.user_id), "user_email": email} for s, email in rows]
    return page_response(items, total, params)


def list_runs(db: Session, params: PageParams, *, status: str | None = None) -> dict:
    stmt = (select(AutomationJob, User.email, AgentDevice.name).join(User, User.id == AutomationJob.user_id)
            .outerjoin(AgentDevice, AgentDevice.id == AutomationJob.device_id)
            .order_by(AutomationJob.created_at.desc(), AutomationJob.id))
    if status == "active":
        stmt = stmt.where(AutomationJob.status.in_(ACTIVE_AUTOMATION_STATUSES))
    elif status:
        stmt = stmt.where(AutomationJob.status == AutomationStatus(status))
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.execute(stmt.limit(params.page_size).offset((params.page - 1) * params.page_size)).all()
    items = [{**automation_service.run_out(r), "user_id": str(r.user_id), "user_email": email, "device": device or ""}
             for r, email, device in rows]
    return page_response(items, total, params)


def stop_run(db: Session, admin: User, run_id: uuid.UUID) -> dict:
    run = db.get(AutomationJob, run_id)
    if run is None:
        raise AppError("NOT_FOUND", "Run not found", 404)
    run = automation_service.stop_run(db, run.user_id, run.id, reason=automation_service.STOP_ADMIN)
    owner = db.get(User, run.user_id)
    _audit(db, admin, "run.stop", owner, run_id=str(run.id))
    db.flush()
    return automation_service.run_out(run)


def list_applications(db: Session, params: PageParams, *, status: str | None = None, q: str | None = None) -> dict:
    stmt = (select(Application, Job, User.email).join(Job, Job.id == Application.job_id)
            .join(User, User.id == Application.user_id).order_by(Application.updated_at.desc(), Application.id))
    if status:
        stmt = stmt.where(Application.status == ApplicationStatus(status))
    if q and q.strip():
        term = _like(q)
        stmt = stmt.where(or_(func.lower(Job.title).like(term, escape="\\"), func.lower(Job.company).like(term, escape="\\"),
                              func.lower(User.email).like(term, escape="\\")))
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.execute(stmt.limit(params.page_size).offset((params.page - 1) * params.page_size)).all()
    items = [{"id": str(a.id), "status": a.status.value, "applied_at": _iso(a.applied_at),
              "updated_at": _iso(a.updated_at), "failure_reason": a.failure_reason[:500],
              "user_id": str(a.user_id), "user_email": email,
              "job": {"title": j.title, "company": j.company, "location": j.location, "job_url": j.job_url}}
             for a, j, email in rows]
    return page_response(items, total, params)


def list_companies(db: Session, params: PageParams, *, q: str | None = None) -> dict:
    """Every company a user targeted in search, or that a search turned up on a job."""
    company_key = func.lower(func.trim(Job.company))
    rows = db.execute(
        select(
            company_key,
            func.max(Job.company),
            func.count(func.distinct(Job.id)),
            func.coalesce(func.sum(case((Application.status == ApplicationStatus.APPLIED, 1), else_=0)), 0),
            func.max(Application.updated_at),
        )
        .select_from(Job)
        .join(Application, Application.job_id == Job.id)
        .where(func.trim(Job.company) != "")
        .group_by(company_key)
    ).all()
    by_key: dict[str, dict] = {}
    for key, name, jobs, applied, last_seen in rows:
        if not key:
            continue
        by_key[key] = {
            "company": (name or "").strip(),
            "jobs": int(jobs or 0),
            "applied": int(applied or 0),
            "last_seen": last_seen,
            "people": {},
            "filter_users": set(),
        }

    for key, user_id, email in db.execute(
        select(company_key, User.id, User.email)
        .select_from(Job)
        .join(Application, Application.job_id == Job.id)
        .join(User, User.id == Application.user_id)
        .where(func.trim(Job.company) != "")
        .distinct()
    ):
        entry = by_key.get(key)
        if entry is not None:
            entry["people"][str(user_id)] = email

    for user_id, companies, updated_at, email in db.execute(
        select(SearchConfig.user_id, SearchConfig.companies, SearchConfig.updated_at, User.email)
        .join(User, User.id == SearchConfig.user_id)
    ):
        if not isinstance(companies, list):
            continue
        for raw in companies:
            name = str(raw).strip()
            if not name:
                continue
            key = name.lower()
            entry = by_key.get(key)
            if entry is None:
                entry = {
                    "company": name,
                    "jobs": 0,
                    "applied": 0,
                    "last_seen": updated_at,
                    "people": {},
                    "filter_users": set(),
                }
                by_key[key] = entry
            entry["filter_users"].add(str(user_id))
            entry["people"][str(user_id)] = email
            if updated_at and (entry["last_seen"] is None or updated_at > entry["last_seen"]):
                entry["last_seen"] = updated_at

    needle = (q or "").strip().lower()
    items = []
    for entry in by_key.values():
        emails = sorted(set(entry["people"].values()))
        if needle and needle not in entry["company"].lower() and not any(needle in email.lower() for email in emails):
            continue
        items.append({
            "company": entry["company"],
            "users": len(entry["people"]),
            "user_emails": emails[:8],
            "jobs": entry["jobs"],
            "applied": entry["applied"],
            "search_filters": len(entry["filter_users"]),
            "last_seen": _iso(entry["last_seen"]),
        })
    items.sort(key=lambda item: (-item["users"], -item["jobs"], -item["applied"], item["company"].lower()))
    start = (params.page - 1) * params.page_size
    return page_response(items[start:start + params.page_size], len(items), params)


def company_detail(db: Session, name: str) -> dict:
    """Overview, jobs with applied counts, and contacts the postings themselves published."""
    from automation.company_contacts import contact_key, extract_published_contacts, merge_contacts

    key = name.strip().lower()
    if not key:
        raise AppError("NOT_FOUND", "Company not found", 404)

    jobs: dict[str, dict] = {}
    published: dict[str, dict] = {}
    display = name.strip()
    locations: set[str] = set()
    last_seen = None
    filter_users: set[str] = set()
    applicants: set[str] = set()

    def touch(when) -> None:
        nonlocal last_seen
        if when and (last_seen is None or when > last_seen):
            last_seen = when

    rows = db.execute(
        select(Job, Application)
        .join(Application, Application.job_id == Job.id)
        .where(func.lower(func.trim(Job.company)) == key)
    ).all()
    for job, application in rows:
        display = (job.company or display).strip() or display
        touch(application.updated_at)
        applicants.add(str(application.user_id))
        if job.location.strip():
            locations.add(job.location.strip())
        bucket = jobs.get(str(job.id))
        if bucket is None:
            bucket = {
                "id": str(job.id),
                "title": job.title,
                "location": job.location,
                "job_url": job.job_url,
                "applied": 0,
                "discovered": 0,
                "users": set(),
                "last_seen": application.updated_at,
            }
            jobs[str(job.id)] = bucket
            for row in merge_contacts(
                list(job.published_contacts or []),
                extract_published_contacts(job.description or ""),
            ):
                ident = contact_key(row)
                if not ident:
                    continue
                entry = published.get(ident)
                if entry is None:
                    entry = {**row, "jobs": []}
                    published[ident] = entry
                if not any(item["title"] == job.title for item in entry["jobs"]):
                    entry["jobs"].append({"title": job.title, "job_url": job.job_url})
        bucket["users"].add(str(application.user_id))
        touch_job = application.updated_at
        if touch_job and (bucket["last_seen"] is None or touch_job > bucket["last_seen"]):
            bucket["last_seen"] = touch_job
        if application.status == ApplicationStatus.APPLIED:
            bucket["applied"] += 1
        else:
            bucket["discovered"] += 1

    for user_id, companies, updated_at in db.execute(
        select(SearchConfig.user_id, SearchConfig.companies, SearchConfig.updated_at)
    ):
        if not isinstance(companies, list):
            continue
        if not any(str(raw).strip().lower() == key for raw in companies):
            continue
        filter_users.add(str(user_id))
        touch(updated_at)

    if not jobs and not filter_users:
        raise AppError("NOT_FOUND", "Company not found", 404)

    applied = sum(job["applied"] for job in jobs.values())
    job_items = [{
        "id": job["id"],
        "title": job["title"],
        "location": job["location"],
        "job_url": job["job_url"],
        "applied": job["applied"],
        "other": job["discovered"],
        "users": len(job["users"]),
        "last_seen": _iso(job["last_seen"]),
    } for job in jobs.values()]
    job_items.sort(key=lambda item: (-item["applied"], -item["users"], item["title"].lower()))

    contact_items = [{
        "name": row["name"],
        "email": row["email"],
        "phone": row["phone"],
        "role": row["role"],
        "link": row["link"],
        "jobs": row["jobs"],
    } for row in published.values()]
    contact_items.sort(key=lambda item: (-int(bool(item["email"] or item["phone"])), item["name"].lower() or item["email"]))

    return {
        "company": display,
        "users": len(applicants),
        "jobs": len(job_items),
        "applied": applied,
        "search_filters": len(filter_users),
        "locations": sorted(locations),
        "last_seen": _iso(last_seen),
        "job_list": job_items,
        "contacts": contact_items,
    }


def list_logs(db: Session, params: PageParams, *, levels: list[str] | None = None, q: str | None = None) -> dict:
    stmt = (select(AutomationLog, User.email).join(User, User.id == AutomationLog.user_id)
            .order_by(AutomationLog.ts.desc(), AutomationLog.id))
    if levels:
        stmt = stmt.where(AutomationLog.level.in_(levels))
    if q and q.strip():
        stmt = stmt.where(func.lower(AutomationLog.message).like(_like(q), escape="\\"))
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.execute(stmt.limit(params.page_size).offset((params.page - 1) * params.page_size)).all()
    items = [{"ts": _iso(log.ts), "level": log.level, "event": log.event, "message": log.message,
              "run_id": str(log.automation_job_id), "user_id": str(log.user_id), "user_email": email}
             for log, email in rows]
    return page_response(items, total, params)


def list_audit(db: Session, params: PageParams) -> dict:
    rows, total = paginate(db, select(AdminAction).order_by(AdminAction.created_at.desc(), AdminAction.id), params)
    items = [{"id": str(a.id), "created_at": _iso(a.created_at), "admin_email": a.admin_email, "action": a.action,
              "target": a.target, "target_user_id": str(a.target_user_id) if a.target_user_id else None,
              "details": a.details} for a in rows]
    return page_response(items, total, params)


# ----------------------------------------------------------------------------- workers
def celery_workers() -> dict:
    """Ping the Celery workers through the broker. Never raises: Redis may simply not be running."""
    try:
        import redis
        # Fail fast: Celery's own connection retries take several seconds when Redis is down.
        redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1).ping()
        from backend.app.worker import celery_app
        with celery_app.connection_for_read() as conn:
            replies = celery_app.control.ping(timeout=1.0, connection=conn) or []
        return {"broker": "ok", "workers": sorted(name for reply in replies for name in reply)}
    except Exception as exc:              # broker down, misconfigured, or celery missing
        logger.info("Celery ping failed: %s", type(exc).__name__)
        return {"broker": "unreachable", "workers": []}


def workers(db: Session, now: datetime | None = None) -> dict:
    now = now or _now()
    rows = db.execute(select(AgentDevice, User.email).join(User, User.id == AgentDevice.user_id)
                      .where(AgentDevice.token_hash.is_not(None), AgentDevice.revoked_at.is_(None))
                      .order_by(AgentDevice.last_seen_at.desc())).all()
    busy = {d for (d,) in db.execute(select(AutomationJob.device_id).where(
        AutomationJob.status.in_(ACTIVE_AUTOMATION_STATUSES), AutomationJob.device_id.is_not(None)))}
    devices = [{**agent_service.device_out(d, now), "user_id": str(d.user_id), "user_email": email,
                "running": d.id in busy} for d, email in rows]
    return {"celery": celery_workers(), "devices": devices}


# ----------------------------------------------------------------------------- email
def settings_overview(db: Session) -> dict:
    from backend.app.services import platform_settings_service as ps

    unverified = db.scalar(select(func.count()).select_from(User).where(User.is_verified.is_(False)))
    view = ps.build_admin_view(db)
    view["unverified_users"] = unverified
    return view


def audit_settings(db: Session, admin: User, action: str, details: dict) -> None:
    _audit(db, admin, action, target_label="platform", **details)


def email_overview(db: Session) -> dict:
    unverified = db.scalar(select(func.count()).select_from(User).where(User.is_verified.is_(False)))
    return {**email_service.email_settings(db), "unverified_users": unverified}


def send_test_template(db: Session, admin: User, sender: email_service.EmailSender, kind: str, to: str) -> dict:
    from backend.app.core.platform_defaults import DEFAULT_EMAIL_TEMPLATES

    settings_now = email_service.email_settings(db)
    if kind not in (DEFAULT_EMAIL_TEMPLATES.get("auth") or {}):
        raise AppError("VALIDATION_ERROR", f"Unknown auth template: {kind}", 422)
    email = email_service.auth_template_test_email(db, kind, to)
    try:
        getattr(sender, "deliver", sender.send)(email)
    except Exception as exc:
        logger.warning("Test template %s to %s failed: %s", kind, to, type(exc).__name__)
        _audit(db, admin, "email.test_template", target_label=to, kind=kind, delivered=False)
        message = str(exc).strip() or "No details from the mail server."
        return {"delivered": False, "mode": settings_now["mode"], "error": f"{type(exc).__name__}: {message}"[:300]}
    _audit(db, admin, "email.test_template", target_label=to, kind=kind, delivered=True)
    return {"delivered": True, "mode": settings_now["mode"], "error": ""}


def broadcast_notifications(
    db: Session,
    admin: User,
    *,
    title: str,
    body: str,
    link: str,
    user_ids: list[uuid.UUID],
) -> dict:
    if link and (not link.startswith("/") or link.startswith("//") or "\\" in link):
        raise AppError("VALIDATION_ERROR", "Link must be an in-app path like /billing.", 422)
    if len(user_ids) > 500:
        raise AppError("VALIDATION_ERROR", "At most 500 users per broadcast.", 422)
    sent = 0
    for uid in user_ids:
        user = db.get(User, uid)
        if user is None or not user.is_active:
            continue
        notification_service.notify_event(
            db,
            uid,
            "admin_broadcast",
            link=link,
            title=title,
            body=body,
            variables={"title": title, "body": body},
        )
        sent += 1
    _audit(db, admin, "notifications.broadcast", target_label="users", count=sent, title=title[:120])
    db.flush()
    return {"sent": sent}


def send_test_email(db: Session, admin: User, sender: email_service.EmailSender, to: str) -> dict:
    """Send right away (not in the background) so the admin sees whether delivery worked."""
    settings_now = email_service.email_settings(db)
    email = email_service.sample_email(to, db)
    try:
        getattr(sender, "deliver", sender.send)(email)
    except Exception as exc:              # SMTP refused, timed out, bad credentials, ...
        logger.warning("Test email to %s failed: %s", to, type(exc).__name__)
        _audit(db, admin, "email.test", target_label=to, delivered=False)
        message = str(exc).strip() or "No details from the mail server."
        return {"delivered": False, "mode": settings_now["mode"], "error": f"{type(exc).__name__}: {message}"[:300]}
    _audit(db, admin, "email.test", target_label=to, delivered=True)
    return {"delivered": True, "mode": settings_now["mode"], "error": ""}


def mark_verified(db: Session, admin: User, user_id: uuid.UUID) -> dict:
    user = _get_user(db, user_id)
    if user.is_verified:
        raise AppError("ALREADY_VERIFIED", "This email address is already verified.", 409)
    user.is_verified = True
    auth_service.invalidate_verification_tokens(db, user.id)
    _audit(db, admin, "user.verify", user)
    db.flush()
    return user_detail(db, user.id)


def resend_verification(db: Session, admin: User, user_id: uuid.UUID) -> tuple[dict, str]:
    """Returns the user detail and a fresh token; the caller emails it."""
    user = _get_user(db, user_id)
    if user.is_verified:
        raise AppError("ALREADY_VERIFIED", "This email address is already verified.", 409)
    if not user.is_active:
        raise AppError("ACCOUNT_DISABLED", "Enable the account before sending it a verification email.", 409)
    token = auth_service.issue_verification_token(db, user)
    _audit(db, admin, "user.resend_verification", user)
    db.flush()
    return user_detail(db, user.id), token


# ----------------------------------------------------------------------------- plans
def _plan_kind(plan: Plan) -> str:
    kind = getattr(plan, "kind", None)
    if kind is None:
        return PLAN_LIMITS.get(plan.code, {}).get("kind", PlanKind.PERSONAL.value)
    return kind.value if hasattr(kind, "value") else str(kind)


def _plan_admin_out(db: Session, plan: Plan, now: datetime) -> dict:
    defaults = PLAN_LIMITS.get(plan.code, {})
    limits = {**defaults, **(plan.limits or {})}
    kind = _plan_kind(plan)
    from backend.app.core.plans import RESUMES_UNLIMITED
    from backend.app.services.usage_service import resume_limit_of

    resumes = resume_limit_of(limits)
    out_limits = {
        "applications_per_month": limits.get("applications_per_month", 0),
        "mock_interviews_per_month": limits.get("mock_interviews_per_month", 0),
        "resumes": resumes,
        "resumes_unlimited": resumes >= RESUMES_UNLIMITED,
    }
    if kind == PlanKind.INSTITUTE.value:
        out_limits["seats"] = int(limits.get("seats") or 0)
    subscribers = db.scalar(select(func.count()).select_from(Subscription)
                            .where(Subscription.plan_id == plan.id, *_entitled_filter(now)))
    return {**billing_service.plan_out(plan), "kind": kind, "is_active": plan.is_active, "sort_order": plan.sort_order,
            "limits": out_limits, "provider_plan_id": plan.provider_plan_id, "subscribers": subscribers}


def list_plans(db: Session) -> list[dict]:
    billing_service.seed_plans(db)
    now = _now()
    return [_plan_admin_out(db, p, now) for p in db.scalars(select(Plan).order_by(Plan.sort_order, Plan.price_cents))]


def _validate_plan_pricing(code: str, price_cents: int, *, is_active: bool) -> None:
    if code == FREE_PLAN:
        if price_cents != 0:
            raise AppError("INVALID_PRICE", "The Free plan must stay free.", 422)
        if not is_active:
            raise AppError("CANNOT_DISABLE_FREE", "The Free plan can't be switched off; everyone falls back to it.", 422)
    elif price_cents > 0 and price_cents < MIN_PAID_PRICE:
        raise AppError("INVALID_PRICE", f"A paid plan must cost at least {MIN_PAID_PRICE / 100:.2f}.", 422)


def create_plan(db: Session, admin: User, provider: PaymentProvider, *, code: str, name: str, kind: str,
                price_cents: int, applications_per_month: int, mock_interviews_per_month: int, is_active: bool,
                sort_order: int, seats: int | None = None, resumes_per_month: int | None = None) -> dict:
    from backend.app.models.enums import PlanKind

    billing_service.seed_plans(db)
    code = code.strip().lower()
    if code == FREE_PLAN:
        raise AppError("RESERVED_CODE", "The code 'free' is reserved for the default plan.", 422)
    if db.scalar(select(Plan).where(Plan.code == code)):
        raise AppError("PLAN_EXISTS", "A plan with that code already exists.", 409)
    _validate_plan_pricing(code, price_cents, is_active=is_active)
    plan_kind = PlanKind.INSTITUTE if kind == PlanKind.INSTITUTE.value else PlanKind.PERSONAL

    limits = {
        "applications_per_month": applications_per_month,
        "mock_interviews_per_month": mock_interviews_per_month,
        "resumes": resumes_per_month if resumes_per_month is not None else PLAN_LIMITS[FREE_PLAN]["resumes"],
    }
    if plan_kind == PlanKind.INSTITUTE:
        seat_count = int(seats if seats is not None else 1)
        if seat_count < 1:
            raise AppError("VALIDATION_ERROR", "Institute plans need at least one seat.", 422)
        limits["seats"] = seat_count
    plan = Plan(
        code=code,
        name=name.strip(),
        kind=plan_kind,
        price_cents=price_cents,
        currency="INR",
        interval="month",
        limits=limits,
        is_active=is_active,
        sort_order=sort_order,
    )
    db.add(plan)
    db.flush()
    if price_cents > 0 and provider.name != "null":
        plan.provider_plan_id = provider.create_plan(plan)
    db.flush()
    out = _plan_admin_out(db, plan, _now())
    _audit(db, admin, "plan.create", target_label=f"plan:{code}", code=code, kind=plan_kind.value, price_cents=price_cents)
    return out


def delete_plan(db: Session, admin: User, code: str) -> dict:
    billing_service.seed_plans(db)
    if code == FREE_PLAN:
        raise AppError("CANNOT_DELETE_FREE", "The Free plan can't be deleted.", 422)
    plan = db.scalar(select(Plan).where(Plan.code == code))
    if plan is None:
        raise AppError("PLAN_NOT_FOUND", "That plan doesn't exist.", 404)
    in_use = db.scalar(select(func.count()).select_from(Subscription).where(Subscription.plan_id == plan.id))
    if in_use:
        raise AppError(
            "PLAN_IN_USE",
            "This plan has subscription history. Hide it instead of deleting.",
            409,
        )
    db.delete(plan)
    db.flush()
    _audit(db, admin, "plan.delete", target_label=f"plan:{code}", code=code)
    return {"deleted": code}


def update_plan(db: Session, admin: User, provider: PaymentProvider, code: str, *, name: str, price_cents: int,
                applications_per_month: int, mock_interviews_per_month: int, is_active: bool, sort_order: int,
                seats: int | None = None, resumes_per_month: int | None = None) -> dict:
    billing_service.seed_plans(db)
    plan = db.scalar(select(Plan).where(Plan.code == code))
    if plan is None:
        raise AppError("PLAN_NOT_FOUND", "That plan doesn't exist.", 404)
    _validate_plan_pricing(code, price_cents, is_active=is_active)

    before = _plan_admin_out(db, plan, _now())
    price_changed = price_cents != plan.price_cents
    plan.name, plan.price_cents, plan.is_active, plan.sort_order = name.strip(), price_cents, is_active, sort_order

    next_limits = {
        "applications_per_month": applications_per_month,
        "mock_interviews_per_month": mock_interviews_per_month,
        "resumes": resumes_per_month if resumes_per_month is not None else before["limits"]["resumes"],
    }
    if _plan_kind(plan) == PlanKind.INSTITUTE.value:
        existing = (plan.limits or {}).get("seats") or PLAN_LIMITS.get(code, {}).get("seats") or 1
        next_limits["seats"] = int(seats if seats is not None else existing)
    plan.limits = next_limits
    if price_changed and code != FREE_PLAN and provider.name != "null":
        # Razorpay plans can't change price: new subscribers get a new plan; existing ones keep theirs.
        plan.provider_plan_id = provider.create_plan(plan)
    db.flush()
    after = _plan_admin_out(db, plan, _now())
    changed = {k: [before[k], after[k]] for k in ("name", "price_cents", "limits", "is_active", "sort_order",
                                                  "provider_plan_id") if before[k] != after[k]}
    if changed:
        _audit(db, admin, "plan.update", target_label=f"plan:{code}", **changed)
    return after
