from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.plans import FREE_PLAN, PLAN_LIMITS
from backend.app.models import Subscription, SubscriptionStatus, User

_ENTITLED = (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def plan_limits(db: Session, user: User) -> dict:
    """Limits of the user's entitled subscription, or the free plan."""
    now = datetime.now(timezone.utc)
    subs = db.scalars(
        select(Subscription).where(Subscription.user_id == user.id, Subscription.status.in_(_ENTITLED))
    ).all()
    for sub in subs:
        if sub.current_period_end is None or _aware(sub.current_period_end) > now:
            defaults = PLAN_LIMITS.get(sub.plan.code, PLAN_LIMITS[FREE_PLAN])
            return {"plan": sub.plan.code, **defaults, **(sub.plan.limits or {})}
    return {"plan": FREE_PLAN, **PLAN_LIMITS[FREE_PLAN]}
