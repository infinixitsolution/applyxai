import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.plans import FREE_PLAN, MOCK_INTERVIEWS_UNLIMITED, PLAN_LIMITS, RESUMES_UNLIMITED
from backend.app.models import MockInterviewSession, Plan, Subscription, SubscriptionStatus, UsageCounter

_ENTITLED = (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING)
_COUNTERS = ("applications", "jobs_discovered", "runtime_seconds", "resumes_created")


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def current_period(now: datetime | None = None) -> str:
    """Usage periods are calendar months in UTC: "YYYY-MM"."""
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m")


def period_bounds(period: str) -> tuple[datetime, datetime]:
    year, month = map(int, period.split("-"))
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = datetime(year + month // 12, month % 12 + 1, 1, tzinfo=timezone.utc)
    return start, end


def plan_limits(db: Session, user_id: uuid.UUID) -> dict:
    """Limits of the user's entitled subscription, or the free plan.

    An active institute seat assignment takes precedence over a personal plan.
    """
    now = datetime.now(timezone.utc)
    from backend.app.services import institute_service
    assignment = institute_service.active_assignment_for_user(db, user_id)
    if assignment is not None and assignment.seat_id:
        seat = db.get(institute_service.InstituteSeat, assignment.seat_id)
        if seat is not None:
            sub = db.get(Subscription, seat.subscription_id)
            if sub is not None and sub.status in _ENTITLED and (
                sub.current_period_end is None or _aware(sub.current_period_end) > now
            ):
                return _limits_of(sub.plan)
    subs = db.scalars(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.institute_id.is_(None),
            Subscription.status.in_(_ENTITLED),
        )
        .order_by(Subscription.created_at.desc())
    ).all()
    for sub in subs:
        if sub.current_period_end is None or _aware(sub.current_period_end) > now:
            return _limits_of(sub.plan)
    free = db.scalar(select(Plan).where(Plan.code == FREE_PLAN))
    return _limits_of(free) if free is not None else {"plan": FREE_PLAN, **PLAN_LIMITS[FREE_PLAN]}


def _limits_of(plan: Plan) -> dict:
    """The catalogue defaults, overridden by what an admin set on the plan row."""
    defaults = PLAN_LIMITS.get(plan.code, PLAN_LIMITS[FREE_PLAN])
    merged = {**defaults, **(plan.limits or {})}
    return {**merged, "plan": plan.code, "name": plan.name, "price_cents": plan.price_cents}


def mock_interviews_used(db: Session, user_id: uuid.UUID, period: str | None = None) -> int:
    start, end = period_bounds(period or current_period())
    return int(
        db.scalar(
            select(func.count())
            .select_from(MockInterviewSession)
            .where(
                MockInterviewSession.user_id == user_id,
                MockInterviewSession.created_at >= start,
                MockInterviewSession.created_at < end,
            )
        )
        or 0
    )


def get_counter(db: Session, user_id: uuid.UUID, period: str | None = None) -> UsageCounter | None:
    return db.scalar(select(UsageCounter).where(UsageCounter.user_id == user_id,
                                                UsageCounter.period == (period or current_period())))


def increment(db: Session, user_id: uuid.UUID, *, now: datetime | None = None, **amounts: int) -> None:
    """
    Atomically add to this month's counters (UPDATE ... SET n = n + x), creating the row on
    first use. Safe with concurrent workers. The caller commits.
    """
    unknown = set(amounts) - set(_COUNTERS)
    if unknown:
        raise ValueError(f"unknown usage counters: {unknown}")
    amounts = {k: v for k, v in amounts.items() if v}
    if not amounts:
        return
    period = current_period(now)
    where = (UsageCounter.user_id == user_id, UsageCounter.period == period)
    values = {k: getattr(UsageCounter, k) + v for k, v in amounts.items()}
    for _ in range(2):
        if db.execute(update(UsageCounter).where(*where).values(**values)).rowcount:
            return
        try:
            with db.begin_nested():
                db.add(UsageCounter(user_id=user_id, period=period,
                                    **{k: amounts.get(k, 0) for k in _COUNTERS}))
            return
        except IntegrityError:
            continue                          # another worker created the row first; update it
    raise RuntimeError("could not record usage")


def usage_summary(db: Session, user_id: uuid.UUID) -> dict:
    limits = plan_limits(db, user_id)
    period = current_period()
    counter = get_counter(db, user_id, period)
    used = counter.applications if counter else 0
    resumes = counter.resumes_created if counter else 0
    app_limit = int(limits["applications_per_month"])
    resume_limit = resume_limit_of(limits)
    mock_limit = int(limits.get("mock_interviews_per_month") or 0)
    mock_used = mock_interviews_used(db, user_id, period)
    mock_remaining = (
        max(mock_limit - mock_used, 0) if mock_limit < MOCK_INTERVIEWS_UNLIMITED else MOCK_INTERVIEWS_UNLIMITED
    )
    return {
        "plan": limits["plan"],
        "plan_name": limits["name"],
        "period": period,
        "resets_at": period_bounds(period)[1].isoformat(),
        "applications": {"used": used, "limit": app_limit, "remaining": max(app_limit - used, 0)},
        "resumes": {
            "used": resumes,
            "limit": resume_limit,
            "remaining": max(resume_limit - resumes, 0),
            "unlimited": resume_limit >= RESUMES_UNLIMITED,
        },
        "mock_interviews": {
            "used": mock_used,
            "limit": mock_limit,
            "remaining": mock_remaining,
            "unlimited": mock_limit >= MOCK_INTERVIEWS_UNLIMITED,
        },
        "jobs_discovered": counter.jobs_discovered if counter else 0,
        "runtime_seconds": counter.runtime_seconds if counter else 0,
        "limit_reached": used >= app_limit,
    }


def remaining_applications(db: Session, user_id: uuid.UUID) -> int:
    return usage_summary(db, user_id)["applications"]["remaining"]


def resume_limit_of(limits: dict) -> int:
    value = limits.get("resumes")
    return RESUMES_UNLIMITED if value is None else int(value)


def resumes_created(db: Session, user_id: uuid.UUID, period: str | None = None) -> int:
    counter = get_counter(db, user_id, period)
    return counter.resumes_created if counter else 0


def ensure_can_create_resume(db: Session, user_id: uuid.UUID) -> None:
    """Raise PLAN_LIMIT_REACHED when this month's resume creations already meet the plan limit."""
    from backend.app.core.errors import AppError

    limit = resume_limit_of(plan_limits(db, user_id))
    if limit >= RESUMES_UNLIMITED:
        return
    if resumes_created(db, user_id) >= limit:
        raise AppError(
            "PLAN_LIMIT_REACHED",
            f"Your plan allows {limit} new resume{'s' if limit != 1 else ''} per month. "
            "Upgrade your plan or wait for next month's reset.",
            status_code=403,
        )
