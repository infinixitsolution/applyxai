import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.core.errors import ok
from backend.app.core.pagination import PageParams, page_params, page_response, paginate
from backend.app.core.rate_limit import RateLimiter, get_rate_limiter
from backend.app.models import MockInterviewSession, User
from backend.app.models.enums import MockInterviewSessionStatus
from backend.app.schemas.mock_interview import (
    MockInterviewCompleteIn,
    MockInterviewCompleteOut,
    MockInterviewFeedbackJobOut,
    MockInterviewCreateIn,
    MockInterviewMessageOut,
    MockInterviewOpeningOut,
    MockInterviewSessionDetail,
    MockInterviewSessionSummary,
    MockInterviewTtsOut,
    MockInterviewTurnIn,
    MockInterviewTurnOut,
)
from backend.app.services import mock_interview_service as svc
from backend.app.services.ai_service import transcribe_audio
from backend.app.services.mock_interview_prompts import MAX_TURNS_BEFORE_END

router = APIRouter(prefix="/mock-interviews", tags=["mock-interviews"])


@router.get("/availability", summary="Whether mock interview AI is configured for your account")
def get_availability(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(svc.availability(db))


def _summary(session: MockInterviewSession) -> MockInterviewSessionSummary:
    fb = session.feedback or {}
    score = fb.get("overall_score") if isinstance(fb, dict) else None
    try:
        overall = int(score) if score is not None else None
    except (TypeError, ValueError):
        overall = None
    timing = svc.session_timing(session)
    remaining = timing.seconds_remaining if session.status == MockInterviewSessionStatus.ACTIVE else None
    return MockInterviewSessionSummary(
        id=session.id,
        application_id=session.application_id,
        interview_types=list(session.interview_types or []),
        status=session.status,
        turn_count=session.turn_count,
        context_snapshot=session.context_snapshot or {},
        feedback=session.feedback,
        created_at=session.created_at,
        updated_at=session.updated_at,
        overall_score=overall,
        max_duration_seconds=timing.max_duration_seconds,
        max_questions=MAX_TURNS_BEFORE_END,
        ends_at=timing.ends_at,
        seconds_remaining=remaining,
    )


def _detail(session: MockInterviewSession) -> MockInterviewSessionDetail:
    base = _summary(session)
    msgs = [
        MockInterviewMessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            meta=m.meta,
            created_at=m.created_at,
        )
        for m in (session.messages or [])
    ]
    return MockInterviewSessionDetail(**base.model_dump(), messages=msgs)


def _job_out(job) -> MockInterviewFeedbackJobOut:
    from backend.app.services.mock_interview_feedback_jobs import job_out

    raw = job_out(job)
    return MockInterviewFeedbackJobOut(
        job_id=uuid.UUID(raw["job_id"]),
        session_id=uuid.UUID(raw["session_id"]),
        operation=raw["operation"],
        status=raw["status"],
        attempt_count=raw["attempt_count"],
        error_code=raw.get("error_code"),
        error_message=raw.get("error_message"),
        presentation_frame_count=raw.get("presentation_frame_count") or 0,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _message_out(msg) -> MockInterviewMessageOut:
    return MockInterviewMessageOut(
        id=msg.id,
        role=msg.role,
        content=msg.content,
        meta=msg.meta,
        created_at=msg.created_at,
    )


@router.get("/sessions", summary="Your mock interview sessions")
def list_sessions(
    params: PageParams = Depends(page_params),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(MockInterviewSession).where(MockInterviewSession.user_id == user.id).order_by(
        MockInterviewSession.created_at.desc()
    )
    rows, total = paginate(db, stmt, params)
    return ok(page_response([_summary(s) for s in rows], total, params))


@router.post("/sessions", summary="Start a mock interview session")
def create_session(
    body: MockInterviewCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    limiter.hit("10/hour", "mock-interview-create", str(user.id))
    session = svc.create_session(db, user, application_id=body.application_id, interview_types=body.interview_types)
    db.commit()
    db.refresh(session)
    return ok(_summary(session))


@router.get("/sessions/{session_id}", summary="One mock interview session with transcript")
def get_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = svc.get_session_detail(db, user.id, session_id)
    return ok(_detail(session))


@router.post("/sessions/{session_id}/opening", summary="Generate the interviewer's opening line")
def opening(
    session_id: uuid.UUID,
    include_audio: bool = Query(True, description="When false, return text only for faster playback via /tts"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    msg, should_end, audio_b64, audio_mime = svc.generate_opening(db, user, session_id, include_audio=include_audio)
    db.commit()
    return ok(
        MockInterviewOpeningOut(
            interviewer_message=_message_out(msg),
            should_end=should_end,
            audio_base64=audio_b64,
            audio_mime=audio_mime,
        )
    )


@router.post("/sessions/{session_id}/turns", summary="Submit your answer and get the next interviewer turn")
def turn(
    session_id: uuid.UUID,
    body: MockInterviewTurnIn,
    include_audio: bool = Query(True, description="When false, return text only for faster playback via /tts"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    limiter.hit("30/minute", "mock-interview-turn", str(user.id))
    cand, interviewer, should_end, audio_b64, audio_mime = svc.append_candidate_turn(
        db,
        user,
        session_id,
        body.content,
        include_audio=include_audio,
        client_turn_id=body.client_turn_id,
    )
    db.commit()
    session = svc.get_session_detail(db, user.id, session_id)
    return ok(
        MockInterviewTurnOut(
            candidate_message=_message_out(cand),
            interviewer_message=_message_out(interviewer),
            should_end=should_end,
            turn_count=session.turn_count,
            audio_base64=audio_b64,
            audio_mime=audio_mime,
        )
    )


def _complete_envelope(
    *,
    session: MockInterviewSession | None = None,
    feedback: dict | None = None,
    job=None,
) -> dict:
    """JSON-serializable envelope (JSONResponse does not encode nested BaseModel)."""
    detail = _detail(session) if session is not None else None
    out = MockInterviewCompleteOut(
        session=detail,
        feedback=feedback,
        job=_job_out(job) if job is not None else None,
    )
    return ok(out.model_dump(mode="json"))


def _feedback_response(db, user, session_id, session, feedback, job):
    from backend.app.services.mock_interview_feedback_jobs import JOB_SUCCEEDED

    if job is None:
        session = svc.get_session_detail(db, user.id, session_id)
        return _complete_envelope(
            session=session,
            feedback=feedback or session.feedback or {},
        )
    if job.status == JOB_SUCCEEDED:
        session = svc.get_session_detail(db, user.id, session_id)
        return _complete_envelope(
            session=session,
            feedback=feedback or session.feedback or {},
            job=job,
        )
    payload = _complete_envelope(job=job)
    return JSONResponse(status_code=202, content=payload)


@router.get("/feedback-jobs/{job_id}", summary="Poll async feedback generation")
def get_feedback_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.app.services.mock_interview_feedback_jobs import get_job

    job = get_job(db, user.id, job_id)
    return ok(_job_out(job))


@router.post("/sessions/{session_id}/regenerate-feedback", summary="Re-run feedback AI on the saved transcript")
def regenerate_feedback(
    session_id: uuid.UUID,
    body: MockInterviewCompleteIn | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    frames = body.presentation_frames if body else []
    session, feedback, job = svc.regenerate_feedback(db, user, session_id, presentation_frames=frames or None)
    db.commit()
    return _feedback_response(db, user, session_id, session, feedback, job)


@router.post("/sessions/{session_id}/complete", summary="End the interview and generate feedback")
def complete(
    session_id: uuid.UUID,
    body: MockInterviewCompleteIn | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    frames = body.presentation_frames if body else []
    session, feedback, job = svc.complete_session(db, user, session_id, presentation_frames=frames or None)
    db.commit()
    return _feedback_response(db, user, session_id, session, feedback, job)


@router.post(
    "/sessions/{session_id}/messages/{message_id}/tts",
    summary="Synthesize speech for a saved interviewer message",
)
def message_tts(
    session_id: uuid.UUID,
    message_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    limiter.hit("60/minute", "mock-interview-tts", str(user.id))
    audio_b64, audio_mime = svc.synthesize_speech_for_message(db, user.id, session_id, message_id)
    db.commit()
    return ok(MockInterviewTtsOut(audio_base64=audio_b64, audio_mime=audio_mime))


@router.post("/transcribe", summary="Transcribe a short audio clip (fallback when browser STT is unavailable)")
async def transcribe(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    limiter.hit("20/minute", "mock-interview-transcribe", str(user.id))
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        from backend.app.core.errors import AppError

        raise AppError("FILE_TOO_LARGE", "Audio must be 8 MB or smaller.", 413)
    name = file.filename or "audio.webm"
    text = transcribe_audio(db, audio_bytes=data, filename=name)
    return ok({"text": text})
