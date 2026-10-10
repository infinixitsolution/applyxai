"""Mock interview session orchestration."""

from __future__ import annotations

import base64
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.app.core.errors import AppError
from backend.app.models import MockInterviewMessage, MockInterviewSession, User
from backend.app.models.enums import InterviewType, MockInterviewMessageRole, MockInterviewSessionStatus
from backend.app.services import ai_service, application_service
from backend.app.services.ai_service import AiTask
from backend.app.services.mock_interview_context import build_interview_context
from backend.app.services.mock_interview_question_plan import prior_interviewer_questions
from backend.app.services.mock_interview_feedback import build_no_answer_feedback, calibrate_feedback
from backend.app.services.mock_interview_rubric_merge import apply_rubric_to_feedback, rubric_feedback_no_answers
from backend.app.services.mock_interview_presentation import (
    analyze_answer_authenticity,
    analyze_presentation_frames,
    merge_presentation_conduct_into_feedback,
    validate_presentation_frames,
)
from backend.app.services.mock_interview_tts import synthesize_interviewer_speech
from backend.app.services.mock_interview_prompts import (
    MAX_TURNS_BEFORE_END,
    MOCK_INTERVIEW_MAX_DURATION_SEC,
    feedback_system_prompt,
    feedback_user_prompt,
    interviewer_system_prompt,
    normalize_interview_types,
    opening_user_prompt,
    turn_user_prompt,
)

logger = logging.getLogger("applyxai.mock_interview")
_FEATURE = "mock_interview"


def _not_found() -> AppError:
    return AppError("NOT_FOUND", "Mock interview session not found.", 404)


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class SessionTiming:
    max_duration_seconds: int
    ends_at: datetime
    seconds_remaining: int
    minutes_remaining: int


def session_timing(session: MockInterviewSession) -> SessionTiming:
    created = _utc(session.created_at)
    ends = created + timedelta(seconds=MOCK_INTERVIEW_MAX_DURATION_SEC)
    remaining = max(0, int((ends - datetime.now(timezone.utc)).total_seconds()))
    minutes = max(0, (remaining + 59) // 60)
    return SessionTiming(MOCK_INTERVIEW_MAX_DURATION_SEC, ends, remaining, minutes)


def _assert_session_time(session: MockInterviewSession) -> SessionTiming:
    timing = session_timing(session)
    if session.status == MockInterviewSessionStatus.ACTIVE and timing.seconds_remaining <= 0:
        raise AppError(
            "SESSION_EXPIRED",
            "The 30-minute interview window has ended. End the interview to generate your feedback report.",
            409,
        )
    return timing


def availability(db: Session) -> dict:
    """Whether mock interviews can run (for candidate UI; never exposes secrets)."""
    from backend.app.services.platform_settings_service import get_effective_ai
    from backend.app.services.platform_settings_service import _row as platform_row

    eff = get_effective_ai(db)
    db_ai = platform_row(db).ai or {}
    if db_ai.get("api_key_encrypted") and not eff.api_key:
        return {
            "available": False,
            "reason": "key_decrypt_failed",
            "message": "The saved API key cannot be read. Re-save it under Admin → Settings → AI (same SECRET_KEY as when it was stored).",
            "voice": False,
        }
    if not eff.enabled:
        return {
            "available": False,
            "reason": "disabled",
            "message": "Platform AI is off. An admin must enable it under Admin → Settings → AI.",
            "voice": False,
        }
    if not eff.configured:
        return {
            "available": False,
            "reason": "no_key",
            "message": "No API key is configured. Add one under Admin → Settings → AI and run Test AI.",
            "voice": False,
        }
    if not eff.features.get("mock_interview"):
        return {
            "available": False,
            "reason": "feature_off",
            "message": "Mock interview is disabled. Turn on Mock interview under Admin → Settings → AI and save.",
            "voice": False,
        }
    voice = eff.provider != "gemini"
    from backend.app.core.platform_defaults import merge_mock_interview_presenter

    presenter = merge_mock_interview_presenter(db_ai.get("mock_interview_presenter"))
    return {
        "available": True,
        "reason": "ready",
        "message": "AI is configured for mock interviews."
        + ("" if voice else " Voice/TTS needs an OpenAI-compatible provider."),
        "voice": voice,
        "provider": eff.provider,
        "presenter": presenter,
    }


def _session(db: Session, user_id: uuid.UUID, session_id: uuid.UUID) -> MockInterviewSession:
    row = db.scalar(
        select(MockInterviewSession)
        .options(selectinload(MockInterviewSession.messages))
        .where(MockInterviewSession.id == session_id, MockInterviewSession.user_id == user_id)
    )
    if row is None:
        raise _not_found()
    return row


def _types_strings(types: list) -> list[str]:
    if not types:
        return ["mixed"]
    out = []
    for t in types:
        out.append(t.value if hasattr(t, "value") else str(t))
    return normalize_interview_types(out)


def _parse_interviewer_json(raw: str) -> tuple[str, bool]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            msg = str(data.get("message") or data.get("content") or "").strip()
            should_end = bool(data.get("should_end"))
            if msg:
                return msg, should_end
    except json.JSONDecodeError:
        pass
    cleaned = raw.strip()
    if cleaned.startswith("{") and '"message"' in cleaned:
        raise AppError("AI_OUTPUT_INVALID", "The interviewer response was malformed. Please try again.", 502)
    if cleaned:
        return cleaned, False
    raise AppError("AI_OUTPUT_INVALID", "The interviewer returned an empty response.", 502)


def _generate_interviewer_reply(db: Session, messages: list[dict[str, str]]) -> tuple[str, bool]:
    last_error: AppError | None = None
    for attempt in range(2):
        raw = ai_service.complete_messages(
            db, AiTask.MOCK_INTERVIEW, messages=messages, feature=_FEATURE, temperature=0.7, max_tokens=320
        )
        try:
            return _parse_interviewer_json(raw)
        except AppError as exc:
            last_error = exc
            if attempt == 0:
                messages = [
                    *messages,
                    {
                        "role": "user",
                        "content": "Your last reply was not valid JSON. Reply again with ONLY "
                        '{"message": "...", "should_end": false} as specified.',
                    },
                ]
    raise last_error or AppError("AI_OUTPUT_INVALID", "The interviewer response was malformed.", 502)


def _messages_for_ai(session: MockInterviewSession) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for msg in session.messages:
        if msg.role == MockInterviewMessageRole.INTERVIEWER:
            out.append({"role": "assistant", "content": msg.content})
        else:
            out.append({"role": "user", "content": msg.content})
    return out


def _segment_meta(types: list[str], turn_count: int) -> dict:
    if types == ["mixed"]:
        order = ["behavioral", "technical", "hr"]
        seg = order[turn_count % len(order)]
        return {"interview_segment": seg}
    return {"interview_segment": types[0] if types else "mixed"}


def _maybe_audio(db: Session, text: str) -> tuple[str, str]:
    try:
        audio = synthesize_interviewer_speech(db, text)
        if audio:
            return base64.b64encode(audio).decode("ascii"), "audio/mpeg"
    except AppError as exc:
        if exc.code in ("AI_UNSUPPORTED", "AI_DISABLED"):
            logger.info("Skipping TTS: %s", exc.code)
        elif exc.code in ("AI_ERROR", "AI_AUTH_FAILED", "AI_RATE_LIMIT"):
            logger.warning("TTS unavailable (%s); continuing with text only.", exc.code)
        else:
            raise
    return "", ""


def create_session(db: Session, user: User, *, application_id: uuid.UUID, interview_types: list[InterviewType]) -> MockInterviewSession:
    if not ai_service.ai_available(db, feature=_FEATURE):
        raise AppError("AI_DISABLED", "Mock interview AI is not enabled.", 503)
    from backend.app.core.plans import MOCK_INTERVIEWS_UNLIMITED
    from backend.app.services.usage_service import mock_interviews_used, plan_limits

    limits = plan_limits(db, user.id)
    cap = int(limits.get("mock_interviews_per_month") or 0)
    if cap <= 0:
        raise AppError(
            "PLAN_LIMIT_REACHED",
            "Your plan does not include mock interviews. Upgrade your plan.",
            403,
        )
    if cap < MOCK_INTERVIEWS_UNLIMITED:
        used = mock_interviews_used(db, user.id)
        if used >= cap:
            raise AppError(
                "PLAN_LIMIT_REACHED",
                f"Your plan allows {cap} mock interview{'s' if cap != 1 else ''} per month. Upgrade or wait until next month.",
                403,
            )
    app = application_service.get_application(db, user.id, application_id)
    ctx, snapshot = build_interview_context(db, user.id, app)
    types = _types_strings([t.value if isinstance(t, InterviewType) else t for t in interview_types])
    session = MockInterviewSession(
        user_id=user.id,
        application_id=app.id,
        interview_types=types,
        status=MockInterviewSessionStatus.ACTIVE,
        turn_count=0,
        context_snapshot={**snapshot, "context_chars": len(ctx)},
    )
    db.add(session)
    db.flush()
    logger.info("mock_interview session created session_id=%s user_id=%s application_id=%s", session.id, user.id, app.id)
    return session


def generate_opening(
    db: Session, user: User, session_id: uuid.UUID, *, include_audio: bool = True
) -> tuple[MockInterviewMessage, bool, str, str]:
    session = _session(db, user.id, session_id)
    if session.status != MockInterviewSessionStatus.ACTIVE:
        raise AppError("SESSION_INACTIVE", "This interview session is not active.", 409)
    timing = _assert_session_time(session)
    if session.messages:
        last = session.messages[-1]
        if last.role == MockInterviewMessageRole.INTERVIEWER:
            audio_b64, audio_mime = _maybe_audio(db, last.content) if include_audio else ("", "")
            return last, False, audio_b64, audio_mime
    app = application_service.get_application(db, user.id, session.application_id)
    ctx, _ = build_interview_context(db, user.id, app)
    types = _types_strings(session.interview_types)
    system = interviewer_system_prompt(
        types=types, context=ctx, turn_count=session.turn_count, minutes_remaining=timing.minutes_remaining
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": opening_user_prompt()}]
    content, should_end = _generate_interviewer_reply(db, messages)
    if timing.minutes_remaining <= 2:
        should_end = True
    msg = MockInterviewMessage(
        session_id=session.id,
        role=MockInterviewMessageRole.INTERVIEWER,
        content=content,
        meta=_segment_meta(types, session.turn_count),
    )
    db.add(msg)
    db.flush()
    audio_b64, audio_mime = _maybe_audio(db, content) if include_audio else ("", "")
    return msg, should_end, audio_b64, audio_mime


def _turn_response_for_idempotency(
    db: Session, session: MockInterviewSession, client_turn_id: uuid.UUID
) -> tuple[MockInterviewMessage, MockInterviewMessage, bool, str, str] | None:
    cand = db.scalar(
        select(MockInterviewMessage).where(
            MockInterviewMessage.session_id == session.id,
            MockInterviewMessage.client_turn_id == client_turn_id,
        )
    )
    if cand is None:
        return None
    interviewer = db.scalar(
        select(MockInterviewMessage)
        .where(
            MockInterviewMessage.session_id == session.id,
            MockInterviewMessage.role == MockInterviewMessageRole.INTERVIEWER,
            MockInterviewMessage.created_at > cand.created_at,
        )
        .order_by(MockInterviewMessage.created_at.asc())
        .limit(1)
    )
    if interviewer is None:
        return None
    audio_b64, audio_mime = "", ""
    meta = interviewer.meta or {}
    cache = meta.get("tts_cache") if isinstance(meta, dict) else None
    if isinstance(cache, dict) and cache.get("audio_base64"):
        audio_b64 = str(cache["audio_base64"])
        audio_mime = str(cache.get("audio_mime") or "audio/mpeg")
    should_end = bool(meta.get("should_end")) if isinstance(meta, dict) else False
    return cand, interviewer, should_end, audio_b64, audio_mime


def append_candidate_turn(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    content: str,
    *,
    include_audio: bool = True,
    client_turn_id: uuid.UUID | None = None,
) -> tuple[MockInterviewMessage, MockInterviewMessage, bool, str, str]:
    session = _session(db, user.id, session_id)
    if session.status != MockInterviewSessionStatus.ACTIVE:
        raise AppError("SESSION_INACTIVE", "This interview session is not active.", 409)
    timing = _assert_session_time(session)
    if client_turn_id is not None:
        cached = _turn_response_for_idempotency(db, session, client_turn_id)
        if cached is not None:
            return cached
    if session.turn_count >= MAX_TURNS_BEFORE_END:
        raise AppError("SESSION_LIMIT", "This interview has reached the maximum number of questions.", 409)
    text = content.strip()
    if not text:
        raise AppError("VALIDATION", "Answer cannot be empty.", 422)
    cand = MockInterviewMessage(
        session_id=session.id,
        role=MockInterviewMessageRole.CANDIDATE,
        content=text,
        client_turn_id=client_turn_id,
    )
    try:
        with db.begin_nested():
            db.add(cand)
            session.turn_count += 1
            db.flush()
    except IntegrityError:
        if client_turn_id is not None:
            cached = _turn_response_for_idempotency(db, session, client_turn_id)
            if cached is not None:
                return cached
        raise AppError("TURN_CONFLICT", "This answer was already submitted. Please wait for the interviewer.", 409)
    db.refresh(session, attribute_names=["messages"])

    app = application_service.get_application(db, user.id, session.application_id)
    ctx, _ = build_interview_context(db, user.id, app)
    types = _types_strings(session.interview_types)
    system = interviewer_system_prompt(
        types=types, context=ctx, turn_count=session.turn_count, minutes_remaining=timing.minutes_remaining
    )
    history = _messages_for_ai(session)
    asked = prior_interviewer_questions(list(session.messages or []))
    messages = [
        {"role": "system", "content": system},
        *history,
        {"role": "user", "content": turn_user_prompt(text, prior_interviewer_lines=asked)},
    ]
    reply, should_end = _generate_interviewer_reply(db, messages)
    if session.turn_count >= MAX_TURNS_BEFORE_END:
        should_end = True
    if timing.minutes_remaining <= 2:
        should_end = True
    meta = _segment_meta(types, session.turn_count)
    meta = {**meta, "should_end": should_end}
    interviewer = MockInterviewMessage(
        session_id=session.id,
        role=MockInterviewMessageRole.INTERVIEWER,
        content=reply,
        meta=meta,
    )
    db.add(interviewer)
    db.flush()
    audio_b64, audio_mime = _maybe_audio(db, reply) if include_audio else ("", "")
    return cand, interviewer, should_end, audio_b64, audio_mime


def synthesize_speech(db: Session, text: str) -> tuple[str, str]:
    return _maybe_audio(db, text)


def synthesize_speech_for_message(db: Session, user_id: uuid.UUID, session_id: uuid.UUID, message_id: uuid.UUID) -> tuple[str, str]:
    session = _session(db, user_id, session_id)
    msg = db.scalar(
        select(MockInterviewMessage).where(
            MockInterviewMessage.id == message_id,
            MockInterviewMessage.session_id == session.id,
        )
    )
    if msg is None:
        raise AppError("NOT_FOUND", "Message not found.", 404)
    if msg.role != MockInterviewMessageRole.INTERVIEWER:
        raise AppError("FORBIDDEN", "Only interviewer lines can be spoken.", 403)
    meta = dict(msg.meta or {})
    cache = meta.get("tts_cache")
    if isinstance(cache, dict) and cache.get("audio_base64"):
        return str(cache["audio_base64"]), str(cache.get("audio_mime") or "audio/mpeg")
    audio_b64, audio_mime = _maybe_audio(db, msg.content)
    if audio_b64:
        meta["tts_cache"] = {"audio_base64": audio_b64, "audio_mime": audio_mime}
        msg.meta = meta
        db.flush()
    return audio_b64, audio_mime


def mark_stale_sessions_abandoned(db: Session, *, idle_hours: int = 24) -> int:
    """Mark long-idle active sessions as abandoned (dashboard filter accuracy)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=idle_hours)
    rows = db.scalars(
        select(MockInterviewSession).where(
            MockInterviewSession.status == MockInterviewSessionStatus.ACTIVE,
            MockInterviewSession.updated_at < cutoff,
        )
    ).all()
    count = 0
    for row in rows:
        row.status = MockInterviewSessionStatus.ABANDONED
        count += 1
    if count:
        db.flush()
    return count


def enqueue_complete(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    *,
    presentation_frames: list[str] | None = None,
):
    from backend.app.services.mock_interview_feedback_jobs import (
        create_feedback_job,
        dispatch_feedback_job,
        JOB_SUCCEEDED,
    )

    session = _session(db, user.id, session_id)
    if session.status == MockInterviewSessionStatus.COMPLETED:
        return session, session.feedback or {}, None
    if session.status != MockInterviewSessionStatus.ACTIVE:
        raise AppError("SESSION_INACTIVE", "This interview session is not active.", 409)
    snap = dict(session.context_snapshot or {})
    if presentation_frames:
        snap["pending_presentation_frames"] = presentation_frames[:12]
        session.context_snapshot = snap
    job = create_feedback_job(db, user=user, session=session, operation="complete", presentation_frames=presentation_frames)
    db.flush()
    job = dispatch_feedback_job(db, job)
    logger.info(
        "mock_interview complete enqueued session_id=%s job_id=%s status=%s",
        session.id,
        job.id,
        job.status,
    )
    if job.status == JOB_SUCCEEDED:
        db.refresh(session)
        return session, session.feedback or {}, job
    return session, None, job


def enqueue_regenerate(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    *,
    presentation_frames: list[str] | None = None,
):
    from backend.app.services.mock_interview_feedback_jobs import (
        create_feedback_job,
        dispatch_feedback_job,
        JOB_SUCCEEDED,
    )

    session = _session(db, user.id, session_id)
    if session.status != MockInterviewSessionStatus.COMPLETED:
        raise AppError("SESSION_ACTIVE", "Finish the interview before regenerating feedback.", 409)
    if not session.messages:
        raise AppError("VALIDATION", "No transcript to analyze.", 422)
    snap = dict(session.context_snapshot or {})
    if presentation_frames:
        snap["pending_presentation_frames"] = presentation_frames[:12]
        session.context_snapshot = snap
    job = create_feedback_job(db, user=user, session=session, operation="regenerate", presentation_frames=presentation_frames)
    db.flush()
    job = dispatch_feedback_job(db, job)
    if job.status == JOB_SUCCEEDED:
        db.refresh(session)
        return session, session.feedback or {}, job
    return session, None, job


def _parse_feedback(db: Session, raw: str) -> dict:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    repair = ai_service.complete_messages(
        db,
        AiTask.MOCK_INTERVIEW_FEEDBACK,
        messages=[
            {"role": "system", "content": "Fix the following into valid JSON only."},
            {"role": "user", "content": text},
        ],
        feature=_FEATURE,
        temperature=0.0,
        max_tokens=2000,
    )
    try:
        data = json.loads(repair.strip().strip("`"))
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        return {"error": "Could not parse feedback", "raw": raw[:8000]}


def merge_regenerated_feedback(prior: dict, fresh: dict) -> dict:
    """
    When regenerating without new camera frames, keep on-camera analysis from the prior report.
    Transcript, rubric, and coaching come from `fresh`; vision sections stay from `prior`.
    """
    prior_pres = prior.get("presentation")
    if isinstance(prior_pres, dict) and prior_pres.get("available") is not False:
        fresh["presentation"] = prior_pres
        fresh = merge_presentation_conduct_into_feedback(fresh, prior_pres)
    prior_meta = prior.get("analysis_meta")
    if isinstance(prior_meta, dict):
        fresh_meta = dict(fresh.get("analysis_meta") or {})
        for key in (
            "presentation_frames_analyzed",
            "behavior_parameters_total",
            "behavior_concerns",
        ):
            if key in prior_meta:
                fresh_meta[key] = prior_meta[key]
        includes = list(fresh_meta.get("includes") or fresh.get("analysis_meta", {}).get("includes") or [])
        if "on_camera_behavior_55" not in includes and prior_pres:
            includes.append("on_camera_behavior_55")
        if "presentation_summary" not in includes and prior_pres:
            includes.append("presentation_summary")
        fresh_meta["includes"] = includes
        fresh["analysis_meta"] = fresh_meta
    return fresh


def _stamp_analysis_meta(session: MockInterviewSession, feedback: dict, *, frames_analyzed: int) -> None:
    from datetime import datetime, timezone

    from backend.app.services.mock_interview_behavior_parameters import BEHAVIOR_ANALYSIS_VERSION
    from backend.app.services.mock_interview_rubric import RUBRIC_VERSION

    presentation = feedback.get("presentation") or {}
    behavioral = presentation.get("behavioral_parameters") or []
    concerns = sum(1 for r in behavioral if r.get("detected") or r.get("status") == "concern")
    candidate_turns = sum(1 for m in (session.messages or []) if m.role == MockInterviewMessageRole.CANDIDATE)
    feedback["analysis_meta"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "message_count": len(session.messages or []),
        "candidate_turns": candidate_turns,
        "presentation_frames_analyzed": frames_analyzed,
        "behavior_parameters_total": 55,
        "behavior_concerns": concerns,
        "rubric_version": RUBRIC_VERSION,
        "behavior_analysis_version": BEHAVIOR_ANALYSIS_VERSION,
        "includes": [
            "transcript_coaching",
            "answer_rubric_100",
            "on_camera_behavior_55",
            "presentation_summary",
            "answer_authenticity",
        ],
    }


def _attach_presentation_and_authenticity(
    db: Session,
    session: MockInterviewSession,
    feedback: dict,
    transcript: str,
    presentation_frames: list[str] | None,
) -> dict:
    frames = validate_presentation_frames(presentation_frames)
    if frames:
        try:
            presentation = analyze_presentation_frames(db, frames)
            feedback["presentation"] = presentation
            feedback = merge_presentation_conduct_into_feedback(feedback, presentation)
            snap = dict(session.context_snapshot or {})
            snap["presentation_frames_analyzed"] = len(frames)
            session.context_snapshot = snap
        except AppError as exc:
            feedback["presentation"] = {
                "available": False,
                "reason": exc.code,
                "presentability_summary": exc.message,
            }
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Presentation analysis parse failed: %s", exc)
            feedback["presentation"] = {"available": False, "reason": "parse_error"}
    elif not feedback.get("presentation"):
        feedback["presentation"] = {
            "available": False,
            "reason": "no_frames",
            "presentability_summary": (
                "Enable your camera during the interview to get expression, eye-contact, and grooming coaching."
            ),
        }
    try:
        feedback["answer_authenticity"] = analyze_answer_authenticity(db, session, transcript)
    except AppError as exc:
        feedback["answer_authenticity"] = {
            "overall": "unknown",
            "confidence": 0,
            "signals": [],
            "notes": exc.message,
        }
    _stamp_analysis_meta(session, feedback, frames_analyzed=len(frames))
    return feedback


def _generate_feedback(
    db: Session, session: MockInterviewSession, user: User, *, presentation_frames: list[str] | None = None
) -> dict:
    app = application_service.get_application(db, user.id, session.application_id)
    ctx, _ = build_interview_context(db, user.id, app)
    types = _types_strings(session.interview_types)
    lines = []
    for msg in session.messages:
        who = "Interviewer" if msg.role == MockInterviewMessageRole.INTERVIEWER else "Candidate"
        lines.append(f"{who}: {msg.content}")
    transcript = "\n".join(lines) or "(No messages recorded.)"
    candidate_turns = sum(1 for m in session.messages if m.role == MockInterviewMessageRole.CANDIDATE)
    if candidate_turns == 0:
        fb = build_no_answer_feedback(session)
        fb.update(rubric_feedback_no_answers(session))
        return _attach_presentation_and_authenticity(db, session, fb, transcript, presentation_frames)

    system = feedback_system_prompt(context=ctx, types=types)
    raw = ai_service.complete_messages(
        db,
        AiTask.MOCK_INTERVIEW_FEEDBACK,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": feedback_user_prompt(transcript, candidate_turns=candidate_turns)},
        ],
        feature=_FEATURE,
        temperature=0.1,
        max_tokens=12000,
    )
    feedback = _parse_feedback(db, raw)
    feedback = calibrate_feedback(session, feedback)
    feedback = apply_rubric_to_feedback(session, feedback)
    return _attach_presentation_and_authenticity(db, session, feedback, transcript, presentation_frames)


def complete_session(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    *,
    presentation_frames: list[str] | None = None,
) -> tuple[MockInterviewSession, dict | None, object | None]:
    return enqueue_complete(db, user, session_id, presentation_frames=presentation_frames)


def regenerate_feedback(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    *,
    presentation_frames: list[str] | None = None,
) -> tuple[MockInterviewSession, dict | None, object | None]:
    return enqueue_regenerate(db, user, session_id, presentation_frames=presentation_frames)


def _overall_score_from_feedback(feedback: dict | None) -> int | None:
    if not isinstance(feedback, dict):
        return None
    score = feedback.get("overall_score")
    if score is None and isinstance(feedback.get("rubric_overall"), (int, float)):
        score = feedback.get("rubric_overall")
    try:
        return int(score) if score is not None else None
    except (TypeError, ValueError):
        return None


def dashboard_stats(db: Session, user_id: uuid.UUID) -> dict:
    """Aggregate mock interview metrics for the candidate home dashboard."""
    from sqlalchemy import func

    from backend.app.models.enums import MockInterviewSessionStatus

    base = MockInterviewSession.user_id == user_id
    by_status = {s.value: 0 for s in MockInterviewSessionStatus}
    for status, count in db.execute(
        select(MockInterviewSession.status, func.count()).where(base).group_by(MockInterviewSession.status)
    ):
        by_status[status.value] = int(count)
    total = sum(by_status.values())

    scores: list[int] = []
    for row in db.scalars(
        select(MockInterviewSession).where(base, MockInterviewSession.status == MockInterviewSessionStatus.COMPLETED)
    ):
        s = _overall_score_from_feedback(row.feedback)
        if s is not None:
            scores.append(s)

    recent: list[dict] = []
    for s in db.scalars(
        select(MockInterviewSession).where(base).order_by(MockInterviewSession.created_at.desc()).limit(5)
    ):
        snap = s.context_snapshot if isinstance(s.context_snapshot, dict) else {}
        recent.append(
            {
                "id": str(s.id),
                "status": s.status.value,
                "turn_count": s.turn_count,
                "overall_score": _overall_score_from_feedback(s.feedback),
                "job_title": str(snap.get("job_title") or ""),
                "company": str(snap.get("company") or ""),
                "created_at": s.created_at.isoformat(),
            }
        )

    return {
        "total": total,
        "by_status": by_status,
        "average_score": round(sum(scores) / len(scores), 1) if scores else None,
        "best_score": max(scores) if scores else None,
        "completed_with_score": len(scores),
        "recent": recent,
    }


def list_sessions(db: Session, user_id: uuid.UUID, *, limit: int = 50, offset: int = 0) -> tuple[list[MockInterviewSession], int]:
    from sqlalchemy import func

    base = select(MockInterviewSession).where(MockInterviewSession.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(MockInterviewSession.created_at.desc()).limit(limit).offset(offset)).all()
    return list(rows), int(total)


def get_session_detail(db: Session, user_id: uuid.UUID, session_id: uuid.UUID) -> MockInterviewSession:
    return _session(db, user_id, session_id)