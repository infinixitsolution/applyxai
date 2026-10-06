import uuid
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, contains_eager

from backend.app.models import Application, ApplicationStatus, AutomationJob, Job
from backend.app.models.enums import ACTIVE_AUTOMATION_STATUSES
from backend.app.services import usage_service
from backend.app.services.automation_service import run_out

CHART_DAYS = 30


def daily_series(db: Session, chart_start: datetime, *filters) -> dict[str, dict[str, int]]:
    """Applied and failed counts per UTC day from `chart_start`, for applications matching `filters`."""
    daily = {(chart_start + timedelta(days=i)).date().isoformat(): {"applied": 0, "failed": 0}
             for i in range(CHART_DAYS)}
    for (applied_at,) in db.execute(select(Application.applied_at).where(
            *filters, Application.status == ApplicationStatus.APPLIED, Application.applied_at >= chart_start)):
        day = applied_at.date().isoformat()
        if day in daily:
            daily[day]["applied"] += 1
    for (updated_at,) in db.execute(select(Application.updated_at).where(
            *filters, Application.status == ApplicationStatus.FAILED, Application.updated_at >= chart_start)):
        day = updated_at.date().isoformat()
        if day in daily:
            daily[day]["failed"] += 1
    return daily


def stats(db: Session, user_id: uuid.UUID, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    today = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    chart_start = today - timedelta(days=CHART_DAYS - 1)
    mine = Application.user_id == user_id

    by_status = {s.value: 0 for s in ApplicationStatus}
    for status, count in db.execute(select(Application.status, func.count()).where(mine).group_by(Application.status)):
        by_status[status.value] = count
    applied, failed = by_status["applied"], by_status["failed"]

    daily = daily_series(db, chart_start, mine)
    applied_today = daily[today.date().isoformat()]["applied"]

    top_companies = [
        {"company": company, "applied": count}
        for company, count in db.execute(
            select(Job.company, func.count()).join(Application, Application.job_id == Job.id)
            .where(mine, Application.status == ApplicationStatus.APPLIED, Job.company != "")
            .group_by(Job.company).order_by(func.count().desc(), Job.company).limit(5))
    ]

    recent = db.scalars(select(Application).join(Application.job).options(contains_eager(Application.job))
                        .where(mine).order_by(Application.updated_at.desc(), Application.id).limit(5)).all()

    runs = AutomationJob.user_id == user_id
    active = db.scalar(select(AutomationJob).where(runs, AutomationJob.status.in_(ACTIVE_AUTOMATION_STATUSES)))
    last = db.scalar(select(AutomationJob).where(runs, AutomationJob.status.not_in(ACTIVE_AUTOMATION_STATUSES))
                     .order_by(AutomationJob.created_at.desc()).limit(1))

    return {
        "applications_by_status": by_status,
        "total_applied": applied,
        "applied_today": applied_today,
        "success_rate": round(applied / (applied + failed), 4) if applied + failed else None,
        "daily": [{"date": d, **v} for d, v in daily.items()],
        "top_companies": top_companies,
        "recent_applications": recent,
        "automation": {"active": run_out(active), "last": run_out(last)},
        "usage": usage_service.usage_summary(db, user_id),
    }
