"""Once-per-day candidate summaries (in-app + optional email via daily_report templates)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, contains_eager

from backend.app.models import Application, ApplicationStatus, User
from backend.app.services import notification_service


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _applied_in_day(start: datetime, end: datetime):
    return and_(
        Application.applied_at.is_not(None),
        Application.applied_at >= start,
        Application.applied_at < end,
    )


def _updated_in_day(start: datetime, end: datetime):
    return and_(Application.updated_at >= start, Application.updated_at < end)


def _activity_filter(start: datetime, end: datetime):
    return or_(_applied_in_day(start, end), _updated_in_day(start, end))


def _count_for_user(db: Session, user_id: uuid.UUID, start: datetime, end: datetime) -> dict[str, int]:
    applied = db.scalar(
        select(func.count())
        .select_from(Application)
        .where(
            Application.user_id == user_id,
            Application.status == ApplicationStatus.APPLIED,
            _applied_in_day(start, end),
        )
    )
    counts: dict[str, int] = {"applied_today": int(applied or 0)}
    for status in (ApplicationStatus.FAILED, ApplicationStatus.SKIPPED, ApplicationStatus.EXTERNAL):
        n = db.scalar(
            select(func.count())
            .select_from(Application)
            .where(
                Application.user_id == user_id,
                Application.status == status,
                _updated_in_day(start, end),
            )
        )
        counts[status.value] = int(n or 0)
    return counts


def _summary_lines(db: Session, user_id: uuid.UUID, start: datetime, end: datetime, limit: int = 20) -> str:
    apps = db.scalars(
        select(Application)
        .join(Application.job)
        .options(contains_eager(Application.job))
        .where(
            Application.user_id == user_id,
            Application.status == ApplicationStatus.APPLIED,
            Application.applied_at >= start,
            Application.applied_at < end,
        )
        .order_by(Application.applied_at.desc(), Application.id.desc())
        .limit(limit)
    ).all()
    if not apps:
        return "No Easy Apply submissions recorded for this day."
    lines = []
    for app in apps:
        title = (app.job.title or "Role").strip()
        company = (app.job.company or "").strip()
        label = f"{title} at {company}" if company else title
        lines.append(f"• {label}")
    if len(apps) >= limit:
        lines.append(f"• … and any others on your Applications page")
    return "\n".join(lines)


def _message_from_counts(counts: dict[str, int]) -> str:
    applied = counts.get("applied_today", 0)
    failed = counts.get("failed", 0)
    skipped = counts.get("skipped", 0)
    external = counts.get("external", 0)
    parts = [f"{applied} applied", f"{failed} failed", f"{skipped} skipped", f"{external} saved external"]
    return ", ".join(parts) + "."


def send_daily_reports(db: Session, report_day: date | None = None) -> int:
    """
    Notify candidates who had application activity on `report_day` (UTC calendar day).
    Defaults to yesterday UTC. Caller commits.
    """
    if report_day is None:
        report_day = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    start, end = _day_bounds(report_day)
    user_ids = db.scalars(
        select(Application.user_id)
        .distinct()
        .where(_activity_filter(start, end))
    ).all()
    sent = 0
    for user_id in user_ids:
        user = db.get(User, user_id)
        if user is None or not user.is_active or not user.is_verified:
            continue
        counts = _count_for_user(db, user_id, start, end)
        if counts.get("applied_today", 0) == 0 and sum(
            counts.get(k, 0) for k in ("failed", "skipped", "external")
        ) == 0:
            continue
        message = _message_from_counts(counts)
        summary = _summary_lines(db, user_id, start, end)
        notification_service.notify_event(
            db,
            user_id,
            "daily_report",
            link="/app/dashboard",
            variables={
                "report_date": report_day.isoformat(),
                "message": message,
                "summary": summary,
                "applied_count": str(counts.get("applied_today", 0)),
                "failed_count": str(counts.get("failed", 0)),
                "skipped_count": str(counts.get("skipped", 0)),
                "external_count": str(counts.get("external", 0)),
            },
        )
        sent += 1
    return sent
