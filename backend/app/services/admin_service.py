"""
Admin-only reads across all users, and the few changes an admin can make. Every change is
recorded in `admin_actions`. Admins never see resume files, application answers, or anything
the payment provider holds (cards, UPI IDs).
"""

import logging
import uuid
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.errors import AppError
from backend.app.core.pagination import PageParams, paginate, page_response
from backend.app.core.plans import FREE_PLAN, PLAN_LIMITS
from backend.app.core.security import hash_password
from backend.app.models import (
    AdminAction, AgentDevice, Application, ApplicationStatus, AutomationJob, AutomationLog, AutomationStatus, Job,
    Payment, Plan, Resume, Subscription, SubscriptionStatus, User, UsageCounter,
)
from backend.app.models.enums import ACTIVE_AUTOMATION_STATUSES, PlanKind
from backend.app.services import (
    agent_service, auth_service, automation_service, billing_service, dashboard_service, email_service,
    notification_service, usage_service,
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

    return {
        "users": users,
        "subscriptions": {"by_plan": [{"code": c, "name": n, "count": k} for c, n, k in by_plan],
                          "mrr_cents": mrr, "past_due": past_due},
        "revenue_30d_cents": revenue,
        "applications": {"this_month_by_status": by_status, "daily": [{"date": d, **v} for d, v in daily.items()]},
        "automation": {"active_runs": active_runs, "last_24h_by_status": runs_by_status,
                       "devices": len(devices), "devices_online": sum(agent_service.is_online(d, now) for d in devices)},
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
    }


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
    out_limits = {"applications_per_month": limits.get("applications_per_month", 0),
                  "resumes": limits.get("resumes", 0)}
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


def update_plan(db: Session, admin: User, provider: PaymentProvider, code: str, *, name: str, price_cents: int,
                applications_per_month: int, resumes: int, is_active: bool, sort_order: int,
                seats: int | None = None) -> dict:
    billing_service.seed_plans(db)
    plan = db.scalar(select(Plan).where(Plan.code == code))
    if plan is None:
        raise AppError("PLAN_NOT_FOUND", "That plan doesn't exist.", 404)
    if code == FREE_PLAN:
        if price_cents != 0:
            raise AppError("INVALID_PRICE", "The Free plan must stay free.", 422)
        if not is_active:
            raise AppError("CANNOT_DISABLE_FREE", "The Free plan can't be switched off; everyone falls back to it.", 422)
    elif price_cents < MIN_PAID_PRICE:
        raise AppError("INVALID_PRICE", f"A paid plan must cost at least {MIN_PAID_PRICE / 100:.2f}.", 422)

    before = _plan_admin_out(db, plan, _now())
    price_changed = price_cents != plan.price_cents
    plan.name, plan.price_cents, plan.is_active, plan.sort_order = name.strip(), price_cents, is_active, sort_order
    next_limits = {"applications_per_month": applications_per_month, "resumes": resumes}
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
