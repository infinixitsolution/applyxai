"""
Automation runs (execution model: the desktop agent on the user's own computer).

    user: start ──► run QUEUED ──► agent claims it (poll) ──► engine events (batches) ──► COMPLETED /
          pause / resume / stop set `run.control`; the agent relays it to the engine        CANCELLED / FAILED

The server never trusts the agent for anything but events: plan limits, readiness, and
ownership are checked here. Each batch carries sequence numbers, so a retried batch is
never applied twice. Runs whose agent goes silent are failed by `reap_stale_runs`
(Celery beat, and lazily whenever the user opens the Automation page).
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from automation import events as ev
from backend.app.core.errors import AppError
from backend.app.models import AgentDevice, AutomationJob, AutomationLog, AutomationStatus, SearchConfig, User
from backend.app.models.enums import ACTIVE_AUTOMATION_STATUSES
from backend.app.services import agent_service, ingest_service, notification_service, preferences_service, run_config_service, usage_service

CONTROL_RUN, CONTROL_PAUSE, CONTROL_STOP = "run", "pause", "stop"
RUN_STALE_SECONDS = 180
QUEUED_EXPIRY = timedelta(hours=24)
MAX_BATCH_EVENTS = 200
RECENT_RUNS = 10

STOP_USER, STOP_PLAN_LIMIT, STOP_ADMIN = "user", "plan_limit", "admin"
_NO_RESUME = "Upload a resume and make it your default."
_LOST_AGENT = ("Lost contact with the desktop agent on your computer. "
               "Everything it reported before that is saved.")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_active(run: AutomationJob) -> bool:
    return run.status in ACTIVE_AUTOMATION_STATUSES


def run_out(run: AutomationJob | None) -> dict | None:
    if run is None:
        return None
    iso = lambda value: value.isoformat() if value else None      # noqa: E731
    return {
        "id": str(run.id), "status": run.status.value, "control": run.control, "dry_run": run.dry_run,
        "created_at": iso(run.created_at), "started_at": iso(run.started_at), "finished_at": iso(run.finished_at),
        "current_job": run.current_job, "total_jobs": run.total_jobs,
        "successful_count": run.successful_count, "failed_count": run.failed_count,
        "skipped_count": run.skipped_count, "error_message": run.error_message, "stop_reason": run.stop_reason,
        "claimed": run.device_id is not None,
    }


def _log(db: Session, run: AutomationJob, level: str, event: str, message: str) -> None:
    seq = db.scalar(select(func.coalesce(func.max(AutomationLog.seq), 0))
                    .where(AutomationLog.automation_job_id == run.id))
    db.add(AutomationLog(automation_job_id=run.id, user_id=run.user_id, seq=seq + 1, ts=_now(),
                         level=level, event=event, message=message))


def _end(db: Session, run: AutomationJob, status: AutomationStatus, message: str, *, notify: bool) -> None:
    run.status = status
    run.finished_at = _now()
    run.current_job = ""
    run.error_message = message if status == AutomationStatus.FAILED else run.error_message
    _log(db, run, "error" if status == AutomationStatus.FAILED else "info", ev.RUN_FINISHED, message)
    if notify:
        title = "Automation run stopped with an error" if status == AutomationStatus.FAILED else "Automation run stopped"
        notification_service.notify_event(
            db, run.user_id, "run_finished", link="/automation",
            variables={"title": title, "message": message},
        )


# --------------------------------------------------------------------------- user side
def get_run(db: Session, user_id: uuid.UUID, run_id: uuid.UUID) -> AutomationJob:
    run = db.scalar(select(AutomationJob).where(AutomationJob.id == run_id, AutomationJob.user_id == user_id))
    if run is None:
        raise AppError("NOT_FOUND", "Automation run not found", 404)
    return run


def active_run(db: Session, user_id: uuid.UUID) -> AutomationJob | None:
    return db.scalar(select(AutomationJob).where(AutomationJob.user_id == user_id,
                                                 AutomationJob.status.in_(ACTIVE_AUTOMATION_STATUSES)))


def readiness(db: Session, user_id: uuid.UUID) -> list[str]:
    problems = run_config_service.readiness_problems(db, user_id)
    if run_config_service.default_resume(db, user_id) is None:
        problems.append(_NO_RESUME)
    return problems


def _resume_tailor_snapshot(db: Session, user_id: uuid.UUID) -> dict:
    from backend.app.services.ai_service import ai_available
    from backend.app.services import resume_ai_service

    search = db.scalar(select(SearchConfig).where(SearchConfig.user_id == user_id))
    raw = (search.extra or {}).get("resume_mode", "default") if search and search.extra else "default"
    mode = raw if raw in ("default", "tailor_if_gate") else "default"
    resume = run_config_service.default_resume(db, user_id)
    ai_on = ai_available(db, feature="resume")
    masters = resume_ai_service.master_skills_ready(db, user_id, resume)
    return {
        "mode": mode,
        "resume_ai_available": ai_on,
        "master_skills_ready": masters,
        "can_tailor": ai_on and masters,
    }


def _persist_resume_mode(db: Session, user_id: uuid.UUID, resume_mode: str) -> None:
    if resume_mode not in ("default", "tailor_if_gate"):
        raise AppError("VALIDATION_ERROR", "resume_mode must be default or tailor_if_gate.", 422)
    if resume_mode == "tailor_if_gate":
        from backend.app.services import resume_ai_service

        snap = _resume_tailor_snapshot(db, user_id)
        if not snap["resume_ai_available"]:
            raise AppError(
                "AI_DISABLED",
                "Resume AI is not enabled. Ask an admin to configure Platform AI → Resume AI, or choose default resume.",
                422,
            )
        resume = run_config_service.default_resume(db, user_id)
        if not resume_ai_service.persist_master_skills_from_profile(db, user_id, resume):
            if not snap["master_skills_ready"]:
                raise AppError(
                    "MASTER_REQUIRED",
                    "Analyze master skills on your default resume before using tailor per job.",
                    422,
                )
    search = db.scalar(select(SearchConfig).where(SearchConfig.user_id == user_id))
    if search is None:
        search = SearchConfig(user_id=user_id, extra={})
        db.add(search)
        db.flush()
    extra = dict(search.extra or {})
    extra["resume_mode"] = resume_mode
    search.extra = extra
    db.flush()


def overview(db: Session, user_id: uuid.UUID) -> dict:
    if reap_stale_runs(db, user_id=user_id):
        db.commit()
    now = _now()
    devices = agent_service.list_devices(db, user_id)
    recent = db.scalars(select(AutomationJob).where(AutomationJob.user_id == user_id)
                        .order_by(AutomationJob.created_at.desc()).limit(RECENT_RUNS)).all()
    problems = readiness(db, user_id)
    return {
        "active": run_out(active_run(db, user_id)),
        "recent": [run_out(r) for r in recent],
        "devices": [agent_service.device_out(d, now) for d in devices],
        "agent_online": any(agent_service.is_online(d, now) for d in devices),
        "readiness": {"ready": not problems, "problems": problems},
        "usage": usage_service.usage_summary(db, user_id),
        "resume_tailor": _resume_tailor_snapshot(db, user_id),
    }


def start_run(db: Session, user: User, *, dry_run: bool = False, resume_mode: str = "default") -> AutomationJob:
    reap_stale_runs(db, user_id=user.id)
    problems = readiness(db, user.id)
    if problems:
        raise AppError("NOT_READY", "Finish setting up before you start: " + " ".join(problems), 422, details=problems)
    if usage_service.remaining_applications(db, user.id) <= 0:
        raise AppError("PLAN_LIMIT_REACHED",
                       "You've used all of this month's applications. Upgrade your plan or wait for the reset.", 403)
    if not agent_service.list_devices(db, user.id):
        raise AppError("NO_AGENT", "Connect the ApplyXAI desktop agent on your computer first.", 409)
    if active_run(db, user.id) is not None:
        raise AppError("RUN_ACTIVE", "A run is already in progress. Stop it before starting another.", 409)
    _persist_resume_mode(db, user.id, resume_mode)
    run = AutomationJob(user_id=user.id, status=AutomationStatus.QUEUED, dry_run=dry_run)
    try:
        with db.begin_nested():
            db.add(run)
    except IntegrityError:
        raise AppError("RUN_ACTIVE", "A run is already in progress. Stop it before starting another.", 409)
    db.flush()
    return run


def _finished_error() -> AppError:
    return AppError("RUN_FINISHED", "This run has already finished.", 409)


def pause_run(db: Session, user_id: uuid.UUID, run_id: uuid.UUID) -> AutomationJob:
    run = get_run(db, user_id, run_id)
    if not is_active(run):
        raise _finished_error()
    if run.status == AutomationStatus.QUEUED:
        raise AppError("RUN_NOT_STARTED", "The run hasn't started yet. Stop it instead if you don't want it.", 409)
    if run.control == CONTROL_STOP:
        raise AppError("RUN_STOPPING", "The run is already stopping.", 409)
    run.control = CONTROL_PAUSE
    return run


def resume_run(db: Session, user_id: uuid.UUID, run_id: uuid.UUID) -> AutomationJob:
    run = get_run(db, user_id, run_id)
    if not is_active(run):
        raise _finished_error()
    if run.control == CONTROL_STOP:
        raise AppError("RUN_STOPPING", "The run is already stopping.", 409)
    run.control = CONTROL_RUN
    return run


def stop_run(db: Session, user_id: uuid.UUID, run_id: uuid.UUID, *, reason: str = STOP_USER) -> AutomationJob:
    run = get_run(db, user_id, run_id)
    if not is_active(run):
        raise _finished_error()
    if run.status == AutomationStatus.QUEUED and run.device_id is None:
        run.control = CONTROL_STOP
        run.stop_reason = reason
        _end(db, run, AutomationStatus.CANCELLED, "Run cancelled before it started.", notify=False)
    elif run.control != CONTROL_STOP:
        run.control = CONTROL_STOP
        run.stop_reason = reason
        if reason == STOP_ADMIN:
            _log(db, run, "warning", "stopping", "ApplyXAI support stopped this run. It ends after the current job.")
    return run


def logs(db: Session, user_id: uuid.UUID, run_id: uuid.UUID, *, after: int = 0, limit: int = 200) -> dict:
    run = get_run(db, user_id, run_id)
    rows = db.scalars(select(AutomationLog).where(AutomationLog.automation_job_id == run.id, AutomationLog.seq > after)
                      .order_by(AutomationLog.seq).limit(limit)).all()
    return {
        "items": [{"seq": r.seq, "ts": r.ts.isoformat(), "level": r.level, "event": r.event, "message": r.message}
                  for r in rows],
        "next_after": rows[-1].seq if rows else after,
    }


# --------------------------------------------------------------------------- agent side
def _fail_claim(db: Session, run: AutomationJob, message: str) -> None:
    _end(db, run, AutomationStatus.FAILED, message, notify=True)


def run_payload(db: Session, run: AutomationJob) -> dict:
    from backend.app.services.ai_service import ai_available

    resume = run_config_service.default_resume(db, run.user_id)
    user = db.get(User, run.user_id)
    doc = preferences_service.application_document(db, user)
    avail = ai_available(db, feature="applications") or ai_available(db, feature="resume")
    search = db.scalar(select(SearchConfig).where(SearchConfig.user_id == run.user_id))
    resume_mode = (search.extra or {}).get("resume_mode", "default") if search and search.extra else "default"
    return {
        "id": str(run.id), "dry_run": run.dry_run, "control": run.control, "next_seq": run.event_seq + 1,
        "values": run_config_service.engine_values(db, run.user_id),
        "resume": None if resume is None else {"id": str(resume.id), "filename": resume.filename,
                                               "file_type": resume.file_type, "file_size": resume.file_size},
        "remaining_applications": usage_service.remaining_applications(db, run.user_id),
        "application_qa": {
            "human_questions": doc["human_questions"],
            "ai_applications_enabled": doc["ai_applications_enabled"],
            "user_information_all": doc["user_information_all"],
            "ai_policy": doc["ai_policy"],
        },
        "ai_available": avail,
        "resume_mode": resume_mode if resume_mode in ("default", "tailor_if_gate") else "default",
    }


def poll(db: Session, device: AgentDevice, *, active_run_id: uuid.UUID | None = None,
         agent_version: str = "", platform: str = "") -> dict | None:
    """
    Heartbeat from an agent. Runs this device holds but no longer reports are failed (the agent
    restarted mid-run). An idle agent gets the user's queued run, if there is one. The caller commits.
    """
    agent_service.touch(device, agent_version=agent_version, platform=platform)
    held = db.scalars(select(AutomationJob).where(AutomationJob.device_id == device.id,
                                                  AutomationJob.status.in_(ACTIVE_AUTOMATION_STATUSES))).all()
    for run in held:
        if run.id != active_run_id:
            _fail_claim(db, run, "The desktop agent restarted during the run. Everything it reported before that is saved.")
    if active_run_id is not None:
        return None

    run = db.scalar(select(AutomationJob).where(AutomationJob.user_id == device.user_id,
                                                AutomationJob.status == AutomationStatus.QUEUED,
                                                AutomationJob.device_id.is_(None))
                    .order_by(AutomationJob.created_at))
    if run is None:
        return None
    claimed = db.execute(update(AutomationJob)
                         .where(AutomationJob.id == run.id, AutomationJob.device_id.is_(None))
                         .values(device_id=device.id, worker_id=str(device.id), last_seen_at=_now())).rowcount
    if not claimed:
        return None                                   # another of the user's computers took it
    db.refresh(run)

    problems = readiness(db, run.user_id)
    if problems:
        _fail_claim(db, run, "The run couldn't start: " + " ".join(problems))
        return None
    if usage_service.remaining_applications(db, run.user_id) <= 0:
        _fail_claim(db, run, "The run couldn't start because this month's application limit is used up.")
        return None
    _log(db, run, "info", "claimed", f"Picked up by {device.name or 'your computer'}. Opening the browser…")
    return run_payload(db, run)


def agent_run(db: Session, device: AgentDevice, run_id: uuid.UUID, *, lock: bool = False) -> AutomationJob:
    stmt = select(AutomationJob).where(AutomationJob.id == run_id, AutomationJob.user_id == device.user_id,
                                       AutomationJob.device_id == device.id)
    run = db.scalar(stmt.with_for_update() if lock else stmt)
    if run is None:
        raise AppError("NOT_FOUND", "Automation run not found", 404)
    return run


def ingest_batch(db: Session, device: AgentDevice, run_id: uuid.UUID, first_seq: int, events: list[dict]) -> dict:
    """
    Apply events numbered first_seq, first_seq + 1, ... Already-applied numbers are skipped;
    a gap is refused so the agent resends from `next_seq`. Returns what the engine should do
    next. The caller commits.
    """
    agent_service.touch(device)
    run = agent_run(db, device, run_id, lock=True)
    expected = run.event_seq + 1
    if first_seq > expected:
        raise AppError("SEQUENCE_GAP", f"Expected events from {expected}.", 409, details={"next_seq": expected})
    fresh = events[expected - first_seq:]

    if fresh:
        live = is_active(run)
        result = ingest_service.ingest_events(db, run.user_id, fresh, run=run if live else None,
                                              context=run.ingest_context)
        run.event_seq += len(fresh)
        if live:
            run.ingest_context = result.context
            if result.finished:
                _record_runtime(db, run)
    run.last_seen_at = _now()

    remaining = usage_service.remaining_applications(db, run.user_id)
    # The engine usually stops itself at the cap (limit_reached); otherwise the server tells it to.
    if fresh and remaining <= 0 and not run.stop_reason and (
            (is_active(run) and run.control != CONTROL_STOP) or run.status == AutomationStatus.CANCELLED):
        run.stop_reason = STOP_PLAN_LIMIT
        if is_active(run):
            run.control = CONTROL_STOP
        if not any(isinstance(e, dict) and e.get("event") == ev.LIMIT_REACHED for e in fresh):
            _log(db, run, "warning", ev.LIMIT_REACHED,
                 "You've reached this month's application limit. Stopping after the current job."
                 if is_active(run) else "You've reached this month's application limit.")
        notification_service.notify_event(
            db,
            run.user_id,
            "limit_reached",
            link="/billing",
            variables={
                "message": "Your automation run stopped. Upgrade your plan to keep applying this month.",
            },
        )
    db.flush()
    return {"next_seq": run.event_seq + 1, "control": run.control if is_active(run) else CONTROL_STOP,
            "status": run.status.value, "remaining_applications": remaining}


def _record_runtime(db: Session, run: AutomationJob) -> None:
    if run.started_at and run.finished_at:
        seconds = int((run.finished_at - run.started_at).total_seconds())
        if seconds > 0:
            usage_service.increment(db, run.user_id, runtime_seconds=seconds)


# --------------------------------------------------------------------------- maintenance
def reap_stale_runs(db: Session, *, now: datetime | None = None, user_id: uuid.UUID | None = None) -> int:
    """Fail claimed runs whose agent went silent; cancel queued runs nobody picked up. The caller commits."""
    now = now or _now()
    scope = [AutomationJob.user_id == user_id] if user_id else []
    silent = db.scalars(select(AutomationJob).where(
        *scope, AutomationJob.status.in_(ACTIVE_AUTOMATION_STATUSES), AutomationJob.device_id.is_not(None),
        AutomationJob.last_seen_at < now - timedelta(seconds=RUN_STALE_SECONDS))).all()
    for run in silent:
        _end(db, run, AutomationStatus.FAILED, _LOST_AGENT, notify=True)
    unclaimed = db.scalars(select(AutomationJob).where(
        *scope, AutomationJob.status == AutomationStatus.QUEUED, AutomationJob.device_id.is_(None),
        AutomationJob.created_at < now - QUEUED_EXPIRY)).all()
    for run in unclaimed:
        _end(db, run, AutomationStatus.CANCELLED,
             "No desktop agent picked up this run within 24 hours, so it was cancelled.", notify=True)
    db.flush()
    return len(silent) + len(unclaimed)
