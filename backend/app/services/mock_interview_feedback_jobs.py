"""Async feedback generation jobs for mock interviews."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.models import MockInterviewFeedbackJob, MockInterviewSession, User
from backend.app.models.enums import MockInterviewSessionStatus

logger = logging.getLogger("applyxai.mock_interview.jobs")

JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_SUCCEEDED = "succeeded"
JOB_FAILED = "failed"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_job(db: Session, user_id: uuid.UUID, job_id: uuid.UUID) -> MockInterviewFeedbackJob:
    row = db.scalar(
        select(MockInterviewFeedbackJob).where(
            MockInterviewFeedbackJob.id == job_id,
            MockInterviewFeedbackJob.user_id == user_id,
        )
    )
    if row is None:
        raise AppError("NOT_FOUND", "Feedback job not found.", 404)
    return row


def create_feedback_job(
    db: Session,
    *,
    user: User,
    session: MockInterviewSession,
    operation: str,
    presentation_frames: list[str] | None,
) -> MockInterviewFeedbackJob:
    frames = presentation_frames or []
    job = MockInterviewFeedbackJob(
        session_id=session.id,
        user_id=user.id,
        operation=operation,
        status=JOB_QUEUED,
        presentation_frame_count=len(frames),
    )
    db.add(job)
    db.flush()
    return job


def run_feedback_job(db: Session, job_id: uuid.UUID) -> None:
    """Execute feedback generation (complete or regenerate). Idempotent for succeeded jobs."""
    from backend.app.services import mock_interview_service as svc

    job = db.get(MockInterviewFeedbackJob, job_id)
    if job is None:
        logger.warning("feedback job missing: %s", job_id)
        return
    if job.status == JOB_SUCCEEDED:
        return

    job.status = JOB_RUNNING
    job.attempt_count += 1
    job.started_at = job.started_at or _now()
    job.error_code = None
    job.error_message = None
    db.flush()

    user = db.get(User, job.user_id)
    if user is None:
        job.status = JOB_FAILED
        job.error_code = "USER_MISSING"
        job.error_message = "User no longer exists."
        job.finished_at = _now()
        return

    session = db.scalar(
        select(MockInterviewSession).where(
            MockInterviewSession.id == job.session_id,
            MockInterviewSession.user_id == job.user_id,
        )
    )
    if session is None:
        job.status = JOB_FAILED
        job.error_code = "SESSION_MISSING"
        job.error_message = "Session not found."
        job.finished_at = _now()
        return

    frames: list[str] | None = None
    snap = session.context_snapshot or {}
    pending = snap.get("pending_presentation_frames")
    if isinstance(pending, list):
        frames = [str(x) for x in pending[:12]]

    prior_feedback = dict(session.feedback or {}) if job.operation == "regenerate" else {}

    try:
        if job.operation == "regenerate":
            if session.status != MockInterviewSessionStatus.COMPLETED:
                raise AppError("SESSION_ACTIVE", "Finish the interview before regenerating feedback.", 409)
            feedback = svc._generate_feedback(db, session, user, presentation_frames=frames)
            if not frames and prior_feedback:
                feedback = svc.merge_regenerated_feedback(prior_feedback, feedback)
            session.feedback = feedback
        else:
            if session.status == MockInterviewSessionStatus.COMPLETED:
                job.status = JOB_SUCCEEDED
                job.finished_at = _now()
                return
            if session.status != MockInterviewSessionStatus.ACTIVE:
                raise AppError("SESSION_INACTIVE", "This interview session is not active.", 409)
            feedback = svc._generate_feedback(db, session, user, presentation_frames=frames)
            session.feedback = feedback
            session.status = MockInterviewSessionStatus.COMPLETED
        if isinstance(session.context_snapshot, dict) and "pending_presentation_frames" in session.context_snapshot:
            cleaned = dict(session.context_snapshot)
            cleaned.pop("pending_presentation_frames", None)
            session.context_snapshot = cleaned
        job.status = JOB_SUCCEEDED
        job.finished_at = _now()
        started = job.started_at or job.created_at
        ms = int((_now() - started).total_seconds() * 1000) if started else 0
        logger.info(
            "mock_interview feedback job succeeded job_id=%s session_id=%s operation=%s duration_ms=%d",
            job.id,
            job.session_id,
            job.operation,
            ms,
        )
    except AppError as exc:
        job.status = JOB_FAILED
        job.error_code = exc.code
        job.error_message = (exc.message or exc.code)[:500]
        job.finished_at = _now()
        logger.warning("feedback job %s failed: %s", job_id, exc.code)
    except Exception as exc:
        job.status = JOB_FAILED
        job.error_code = "INTERNAL_ERROR"
        job.error_message = "Report generation failed."
        job.finished_at = _now()
        logger.exception("feedback job %s error", job_id)


def dispatch_feedback_job(db: Session, job: MockInterviewFeedbackJob) -> MockInterviewFeedbackJob:
    """Queue Celery task or run synchronously when the broker is unavailable."""
    db.commit()
    try:
        from backend.app.worker import run_mock_interview_feedback_job

        run_mock_interview_feedback_job.delay(str(job.id))
    except Exception:
        logger.info("Celery unavailable; running feedback job %s inline", job.id)
        run_feedback_job(db, job.id)
        db.commit()
        db.refresh(job)
    return job


def job_out(job: MockInterviewFeedbackJob) -> dict:
    return {
        "job_id": str(job.id),
        "session_id": str(job.session_id),
        "operation": job.operation,
        "status": job.status,
        "attempt_count": job.attempt_count,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "presentation_frame_count": job.presentation_frame_count,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }
