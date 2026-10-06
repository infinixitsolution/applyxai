"""
Turns engine events (automation/events.py) into jobs, applications, run counters, run logs,
and notifications. Live runs and imported CSV history go through the same code.

`failed` and `skipped` events carry only the job id, so the title and company come from the
`job_started` event the engine sends first; `context` carries those between batches.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from automation import events as ev
from backend.app.models import ApplicationStatus, AutomationJob, AutomationLog, AutomationStatus
from backend.app.services import application_service, notification_service

_STATUS_FOR_OUTCOME = {
    ev.APPLIED: ApplicationStatus.APPLIED,
    ev.EXTERNAL: ApplicationStatus.EXTERNAL,
    ev.FAILED: ApplicationStatus.FAILED,
    ev.SKIPPED: ApplicationStatus.SKIPPED,
}
_JOB_URL = "https://www.linkedin.com/jobs/view/{}"


@dataclass
class IngestResult:
    applied: int = 0
    external: int = 0
    failed: int = 0
    skipped: int = 0
    finished: bool = False
    context: dict = field(default_factory=dict)


def _text(value, limit: int) -> str:
    return "" if value is None else str(value).strip()[:limit]


def _job_label(details: dict) -> str:
    title, company = _text(details.get("title"), 200), _text(details.get("company"), 200)
    return f"{title} at {company}" if title and company else title or f"job {details.get('job_id')}"


def _record_outcome(db: Session, user_id: uuid.UUID, event: dict, details: dict,
                    run: AutomationJob | None, count_usage: bool) -> None:
    job_id = _text(event["job_id"], 64)
    job_url = _text(details.get("job_link"), 1024)
    if not job_url.startswith("https://"):
        job_url = _JOB_URL.format(job_id)
    job = application_service.upsert_job(
        db, external_id=job_id,
        title=_text(details.get("title"), 500) or f"LinkedIn job {job_id}",
        company=_text(details.get("company"), 255),
        location=_text(details.get("work_location"), 255),
        work_setting=_text(details.get("work_style"), 32),
        job_url=job_url,
        description=_text(details.get("description"), 100_000),
    )
    status = _STATUS_FOR_OUTCOME[event["event"]]
    reason = ""
    if status in (ApplicationStatus.FAILED, ApplicationStatus.SKIPPED):
        reason = _text(event.get("reason"), 500)
        detail = _text(event.get("detail"), 1000)
        if status == ApplicationStatus.FAILED and detail and detail != reason:
            reason = f"{reason}: {detail}" if reason else detail
    applied_at = None
    if status == ApplicationStatus.APPLIED:
        applied_at = ev.parse_time(event.get("date_applied")) or ev.parse_time(event.get("ts"))
    application_service.record_application(
        db, user_id, job, status, automation_job_id=run.id if run else None,
        failure_reason=reason, applied_at=applied_at, count_usage=count_usage,
    )


def _stopped_message(stop_reason: str) -> str:
    if stop_reason == "user":
        return "Run stopped at your request."
    if stop_reason == "plan_limit":
        return "Run stopped at this month's application limit."
    return "Run stopped."


def _log_message(event: dict, details: dict, stop_reason: str = "") -> tuple[str, str]:
    kind = event["event"]
    if kind == ev.RUN_STARTED:
        terms = ", ".join(_text(t, 100) for t in (event.get("search_terms") or [])[:10])
        return "info", f"Run started. Searching for: {terms}" if terms else "Run started."
    if kind == ev.LOGIN_REQUIRED:
        return "warning", "Sign in to LinkedIn in the browser window ApplyXAI opened. The run continues once you're signed in."
    if kind == ev.JOB_STARTED:
        return "info", f"Looking at {_job_label(details)}."
    if kind == ev.APPLIED:
        return "info", f"Applied to {_job_label(details)}."
    if kind == ev.EXTERNAL:
        return "info", f"{_job_label(details)} uses an external application site. Saved so you can apply yourself."
    if kind == ev.FAILED:
        return "error", f"Couldn't apply to {_job_label(details)}: {_text(event.get('reason'), 300) or 'unknown error'}."
    if kind == ev.SKIPPED:
        return "info", f"Skipped {_job_label(details)}: {_text(event.get('reason'), 300) or 'filtered out'}."
    if kind == ev.PAUSED:
        return "info", "Paused."
    if kind == ev.RESUMED:
        return "info", "Resumed."
    if kind == ev.LIMIT_REACHED:
        return "warning", "You've reached this month's application limit, so the run is stopping."
    if kind == ev.RUN_FINISHED:
        if event.get("error"):
            return "error", f"Run stopped because of an error: {_text(event.get('error'), 500)}"
        return "info", _stopped_message(stop_reason) if event.get("stopped") else "Run finished."
    return "info", kind


def _finish(db: Session, run: AutomationJob, event: dict, at: datetime) -> None:
    run.finished_at = at
    run.current_job = ""
    if event.get("error"):
        run.status = AutomationStatus.FAILED
        run.error_message = _text(event.get("error"), 2000)
    elif event.get("stopped"):
        run.status = AutomationStatus.CANCELLED
    else:
        run.status = AutomationStatus.COMPLETED
    applied, external = int(event.get("applied") or 0), int(event.get("external") or 0)
    body = f"{applied} applied, {external} external, {int(event.get('failed') or 0)} failed, {int(event.get('skipped') or 0)} skipped."
    title = {AutomationStatus.FAILED: "Automation run stopped with an error",
             AutomationStatus.CANCELLED: "Automation run stopped"}.get(run.status, "Automation run finished")
    notification_service.notify(db, run.user_id, "run_finished", title, body, "/automation")


def ingest_events(db: Session, user_id: uuid.UUID, events: list[dict], *,
                  run: AutomationJob | None = None, context: dict | None = None,
                  count_usage: bool = True) -> IngestResult:
    """
    Apply a batch of events for `user_id`. With `run`, also update that run's status,
    counters, and log. Pass the previous result's `context` with the next batch of the
    same run. Imported history uses count_usage=False so it doesn't use up this month's
    plan limit. The caller commits.
    """
    if run is not None and run.user_id != user_id:
        raise ValueError("automation run does not belong to this user")
    result = IngestResult(context=dict(context or {}))
    seq = 0
    limit_reached = False
    if run is not None:
        seq = db.scalar(select(func.coalesce(func.max(AutomationLog.seq), 0))
                        .where(AutomationLog.automation_job_id == run.id))

    for raw in events:
        event = ev.validate_event(raw)
        if event is None:
            continue
        kind = event["event"]
        at = ev.parse_time(event.get("ts")) or datetime.now(timezone.utc)
        details = {}
        if "job_id" in event:
            key = str(event["job_id"])
            details = {**result.context.get(key, {}), **{k: v for k, v in event.items() if v not in (None, "")}}
            if kind == ev.JOB_STARTED:
                result.context[key] = {k: details.get(k) for k in ("title", "company", "work_location", "work_style")}

        if kind in _STATUS_FOR_OUTCOME:
            _record_outcome(db, user_id, event, details, run, count_usage)
            setattr(result, kind, getattr(result, kind) + 1)
            result.context.pop(str(event["job_id"]), None)

        if run is None:
            continue
        if kind == ev.RUN_STARTED:
            run.status = AutomationStatus.RUNNING
            run.started_at = run.started_at or at
        elif kind == ev.JOB_STARTED:
            run.current_job = _job_label(details)[:500]
        elif kind == ev.PAUSED:
            run.status = AutomationStatus.PAUSED
        elif kind == ev.RESUMED:
            run.status = AutomationStatus.RUNNING
        elif kind in _STATUS_FOR_OUTCOME:
            run.total_jobs += 1
            if kind == ev.APPLIED:
                run.successful_count += 1
            elif kind == ev.FAILED:
                run.failed_count += 1
            elif kind == ev.SKIPPED:
                run.skipped_count += 1
        elif kind == ev.RUN_FINISHED:
            _finish(db, run, event, at)
            result.finished = True
        elif kind == ev.LIMIT_REACHED:
            if run.stop_reason:
                continue                                # the server already logged why the run is stopping
            limit_reached = True

        stop_reason = "plan_limit" if limit_reached and not run.stop_reason else run.stop_reason
        level, message = _log_message(event, details, stop_reason)
        seq += 1
        db.add(AutomationLog(automation_job_id=run.id, user_id=user_id, seq=seq, ts=at,
                             level=level, event=kind, message=message))
    db.flush()
    return result
