import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.plans import FREE_PLAN, PLAN_LIMITS
from backend.app.models import Resume, Subscription, SubscriptionStatus, UsageCounter

_ENTITLED = (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING)
_COUNTERS = ("applications", "jobs_discovered", "runtime_seconds")


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
    """Limits of the user's entitled subscription, or the free plan."""
    now = datetime.now(timezone.utc)
    subs = db.scalars(
        select(Subscription).where(Subscription.user_id == user_id, Subscription.status.in_(_ENTITLED))
    ).all()
    for sub in subs:
        if sub.current_period_end is None or _aware(sub.current_period_end) > now:
            defaults = PLAN_LIMITS.get(sub.plan.code, PLAN_LIMITS[FREE_PLAN])
            return {"plan": sub.plan.code, **defaults, **(sub.plan.limits or {})}
    return {"plan": FREE_PLAN, **PLAN_LIMITS[FREE_PLAN]}


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
    resumes = db.scalar(select(func.count()).select_from(Resume).where(Resume.user_id == user_id))
    app_limit, resume_limit = limits["applications_per_month"], limits["resumes"]
    return {
        "plan": limits["plan"],
        "plan_name": limits["name"],
        "period": period,
        "resets_at": period_bounds(period)[1].isoformat(),
        "applications": {"used": used, "limit": app_limit, "remaining": max(app_limit - used, 0)},
        "resumes": {"used": resumes, "limit": resume_limit, "remaining": max(resume_limit - resumes, 0)},
        "jobs_discovered": counter.jobs_discovered if counter else 0,
        "runtime_seconds": counter.runtime_seconds if counter else 0,
        "limit_reached": used >= app_limit,
    }


def remaining_applications(db: Session, user_id: uuid.UUID) -> int:
    return usage_summary(db, user_id)["applications"]["remaining"]
