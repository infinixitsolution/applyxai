"""Live interview sessions: profile-voice answers, transcript, and a written report."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.models import Application, Job, LiveInterviewSession, LiveInterviewToken, User, UserProfile
from backend.app.models.enums import ApplicationStatus
from backend.app.services.ai_service import AiTask, complete, stream_complete, transcribe_audio
from backend.app.services.platform_settings_service import get_effective_ai


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _candidate_name(user: User) -> str:
    name = f"{user.first_name} {user.last_name}".strip()
    return name or "I"


def _profile_brief(user: User, profile: UserProfile | None, job_title: str, company: str, description: str) -> str:
    lines = [f"Name: {_candidate_name(user)}"]
    if profile is not None:
        if profile.headline:
            lines.append(f"Headline: {profile.headline}")
        if profile.current_title or profile.current_company:
            lines.append(f"Current role: {profile.current_title} at {profile.current_company}".strip())
        if profile.experience_years:
            lines.append(f"Years of experience: {profile.experience_years}")
        if profile.summary:
            lines.append(f"Summary: {profile.summary[:1500]}")
        if profile.skills:
            lines.append("Skills: " + ", ".join(str(s) for s in profile.skills[:40]))
        if profile.work_history:
            lines.append("Work history: " + json.dumps(profile.work_history)[:2000])
        if profile.education:
            lines.append("Education: " + json.dumps(profile.education)[:800])
    if job_title or company:
        lines.append(f"This interview is for: {job_title} at {company}".strip())
    if description:
        lines.append("Job description:\n" + description[:2500])
    return "\n".join(lines)


def _ai_ready(db: Session) -> None:
    cfg = get_effective_ai(db)
    if cfg.enabled and cfg.configured and (cfg.feature_on("applications") or cfg.feature_on("mock_interview")):
        return
    raise AppError("AI_DISABLED", "Platform AI is not enabled. An admin needs to turn it on under Settings → AI.", 503)


def _feature(db: Session) -> str:
    cfg = get_effective_ai(db)
    if cfg.feature_on("applications"):
        return "applications"
    return "mock_interview"


def session_out(session: LiveInterviewSession, *, token_code: str = "") -> dict:
    return {
        "id": str(session.id),
        "status": session.status,
        "job_title": session.job_title,
        "company": session.company,
        "application_id": str(session.application_id) if session.application_id else None,
        "token": token_code,
        "transcript": session.transcript or [],
        "feedback": session.feedback,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
    }


def _token_for_user(db: Session, user_id: uuid.UUID, code: str) -> LiveInterviewToken:
    cleaned = "".join(ch for ch in code if ch.isdigit())
    if len(cleaned) != 8:
        raise AppError("INVALID_TOKEN", "Enter the 8-digit token from support chat.", 422)
    token = db.scalar(select(LiveInterviewToken).where(LiveInterviewToken.code == cleaned))
    if token is None or token.user_id != user_id:
        raise AppError("INVALID_TOKEN", "That token is not on this account.", 404)
    return token


def list_applications(db: Session, user_id: uuid.UUID) -> list[dict]:
    """Jobs this candidate's auto-apply run actually submitted."""
    rows = db.execute(
        select(Application, Job)
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.user_id == user_id,
            Application.status == ApplicationStatus.APPLIED,
            Application.automation_job_id.is_not(None),
        )
        .order_by(Application.applied_at.desc(), Application.created_at.desc())
        .limit(50)
    ).all()
    return [
        {"id": str(app.id), "title": job.title, "company": job.company}
        for app, job in rows
    ]


def start_session(db: Session, user: User, *, code: str, application_id: uuid.UUID | None) -> dict:
    token = _token_for_user(db, user.id, code)
    if token.status == "used":
        raise AppError("TOKEN_USED", "This token was already used for a finished interview.", 409)
    if token.status == "reserved" and token.session_id:
        existing = db.get(LiveInterviewSession, token.session_id)
        if existing is not None and existing.status == "active":
            return session_out(existing, token_code=token.code)
    job_title, company, description = "", "", ""
    if application_id is not None:
        app = db.get(Application, application_id)
        if app is None or app.user_id != user.id:
            raise AppError("NOT_FOUND", "That application was not found.", 404)
        job = db.get(Job, app.job_id)
        if job is not None:
            job_title, company, description = job.title, job.company, job.description or ""
    session = LiveInterviewSession(
        user_id=user.id,
        token_id=token.id,
        application_id=application_id,
        job_title=job_title,
        company=company,
        status="active",
        transcript=[],
        started_at=_now(),
    )
    db.add(session)
    db.flush()
    token.status = "reserved"
    token.session_id = session.id
    session.feedback = {"job_description": description[:4000]} if description else None
    return session_out(session, token_code=token.code)


def _append(session: LiveInterviewSession, role: str, text: str) -> dict:
    turn = {"role": role, "text": text.strip(), "at": _now().isoformat()}
    session.transcript = [*(session.transcript or []), turn]
    return turn


def _suggest(db: Session, user: User, session: LiveInterviewSession, question: str) -> str:
    system, user_prompt = _suggest_prompts(db, user, session, question)
    return complete(
        db, AiTask.MOCK_INTERVIEW, system=system, user=user_prompt,
        feature=_feature(db), temperature=0.4, max_tokens=_ANSWER_TOKENS,
    ).strip()


_ANSWER_TOKENS = 300


def _suggest_prompts(db: Session, user: User, session: LiveInterviewSession, question: str) -> tuple[str, str]:
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    description = ""
    if isinstance(session.feedback, dict):
        description = str(session.feedback.get("job_description") or "")
    brief = _profile_brief(user, profile, session.job_title, session.company, description)
    history = []
    for turn in (session.transcript or [])[-12:]:
        history.append(f"{turn.get('role')}: {turn.get('text')}")
    system = (
        "You write the words a candidate will read aloud, in English, during a live job interview. "
        "Write in the first person as this candidate, using their real name, experience, and technologies. "
        "Use short spoken sentences a person can say without looking away for long. "
        "3 to 6 sentences. Plain English only. If the interviewer speaks another language, still answer in English. "
        "No bullet points, labels, stage directions, or preamble."
    )
    user_prompt = (
        f"Candidate profile:\n{brief}\n\n"
        f"Conversation so far:\n" + ("\n".join(history) or "(none)") + "\n\n"
        f"Interviewer just asked:\n{question}\n\n"
        "Write the candidate's spoken English answer."
    )
    return system, user_prompt


def stream_answer(db: Session, user: User, session_id: uuid.UUID) -> Iterator[str]:
    """Stream the answer to the latest interviewer question, then save it to the transcript.

    The first piece is fetched before returning, so setup errors surface as normal API errors.
    """
    session = _active_session(db, user, session_id)
    transcript = session.transcript or []
    if not transcript or transcript[-1].get("role") != "interviewer":
        raise AppError("NO_QUESTION", "There is no new interviewer question to answer.", 409)
    _ai_ready(db)
    system, user_prompt = _suggest_prompts(db, user, session, str(transcript[-1].get("text") or ""))
    pieces = stream_complete(
        db, AiTask.MOCK_INTERVIEW, system=system, user=user_prompt,
        feature=_feature(db), temperature=0.4, max_tokens=_ANSWER_TOKENS,
    )
    first = next(pieces, "")
    question_count = len(transcript)
    bind = db.get_bind()

    def run() -> Iterator[str]:
        written = [first]
        if first:
            yield first
        for piece in pieces:
            written.append(piece)
            yield piece
        answer = "".join(written).strip()
        if not answer:
            return
        # The request's session is closed once streaming starts, so the save uses its own.
        with Session(bind=bind, expire_on_commit=False) as save_db:
            saved = save_db.get(LiveInterviewSession, session_id)
            if saved is None or saved.status != "active":
                return
            turns = list(saved.transcript or [])
            turns.insert(min(question_count, len(turns)), {"role": "suggestion", "text": answer, "at": _now().isoformat()})
            saved.transcript = turns
            save_db.commit()

    return run()


def _active_session(db: Session, user: User, session_id: uuid.UUID) -> LiveInterviewSession:
    session = db.get(LiveInterviewSession, session_id)
    if session is None or session.user_id != user.id:
        raise AppError("NOT_FOUND", "That interview was not found.", 404)
    if session.status != "active":
        raise AppError("SESSION_CLOSED", "This interview has already ended.", 409)
    return session


_HALLUCINATIONS = (
    "thank you for watching",
    "thanks for watching",
    "please subscribe",
    "subtitles by",
    "translated by",
    "transcribe only the english words",
    "use only the english words",
    "english job interview",
    "subscribe to learn english",
    "engvid.com",
    "complete disclaimer at",
    "covid-19 safety guidelines",
    "please post them in the comments",
)
_FILLER = {"thank you", "thank you.", "thanks.", "thanks", "you", "bye.", "bye", "okay.", "okay"}


def _english_transcript(text: str) -> str:
    """Keep Latin-script English. Drop other scripts and common silent-clip hallucinations."""
    cleaned = " ".join((text or "").split())
    lowered = cleaned.lower()
    if any(phrase in lowered for phrase in _HALLUCINATIONS) or lowered in _FILLER:
        return ""
    letters = [ch for ch in cleaned if ch.isalpha()]
    if not letters:
        return ""
    latin = [ch for ch in letters if "a" <= ch.lower() <= "z"]
    if len(latin) / len(letters) < 0.85:
        return ""
    return cleaned


def add_clip(
    db: Session, user: User, session_id: uuid.UUID, *, speaker: str, audio: bytes, filename: str,
    defer_answer: bool = False,
) -> dict:
    """Transcribe one clip. With defer_answer, the caller streams the answer from stream_answer instead."""
    session = _active_session(db, user, session_id)
    if speaker not in ("interviewer", "candidate"):
        raise AppError("VALIDATION_ERROR", "Speaker must be interviewer or candidate.", 422)
    _ai_ready(db)
    text = transcribe_audio(
        db,
        audio_bytes=audio,
        filename=filename or "clip.wav",
        feature=_feature(db),
        language="en",
    ).strip()
    text = _english_transcript(text)
    added: list[dict] = []
    if len(text) < 8:
        return {"turns": [], "transcript": session.transcript or []}
    added.append(_append(session, speaker, text))
    if speaker == "interviewer" and defer_answer:
        return {"turns": added, "transcript": session.transcript or [], "answer_pending": True}
    if speaker == "interviewer":
        answer = _suggest(db, user, session, text)
        if answer:
            added.append(_append(session, "suggestion", answer))
    return {"turns": added, "transcript": session.transcript or []}


def _parse_feedback(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[: text.rfind("```")]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        data = json.loads(text[start:end + 1]) if start >= 0 and end > start else {}
    if not isinstance(data, dict):
        data = {}
    score = data.get("overall_score")
    try:
        score = max(0, min(100, int(score)))
    except (TypeError, ValueError):
        score = None
    dims = data.get("dimensions") if isinstance(data.get("dimensions"), list) else []
    samples = data.get("sample_answers") if isinstance(data.get("sample_answers"), list) else []
    suggestions = data.get("suggestions") if isinstance(data.get("suggestions"), list) else []
    improvements = data.get("improvements") if isinstance(data.get("improvements"), list) else []
    if not suggestions:
        suggestions = improvements
    summary = str(data.get("summary") or data.get("knowledge_summary") or "")[:2000]
    breakdown = data.get("question_breakdown") if isinstance(data.get("question_breakdown"), list) else []
    return {
        "overall_score": score,
        "summary": summary,
        "knowledge_summary": str(data.get("knowledge_summary") or summary)[:2000],
        "dimensions": dims[:8],
        "strengths": [str(s) for s in (data.get("strengths") or [])][:8] if isinstance(data.get("strengths"), list) else [],
        "suggestions": [str(s) for s in suggestions][:8],
        "sample_answers": samples[:8],
        "question_breakdown": breakdown[:20],
        "rubric_scores": data.get("rubric_scores") if isinstance(data.get("rubric_scores"), list) else [],
    }


def _apply_mock_rubric(report: dict, *, substantive: bool, empty_note: str = "No meaningful candidate answers.") -> dict:
    from backend.app.services.mock_interview_rubric import (
        RUBRIC_VERSION,
        empty_rubric_scores,
        legacy_dimensions_from_rubric,
        normalize_rubric_scores,
        rubric_categories_from_scores,
    )

    scores = normalize_rubric_scores(report.get("rubric_scores"))
    if not substantive:
        scores = empty_rubric_scores(score=0, note=empty_note)
    report["rubric_version"] = RUBRIC_VERSION
    report["rubric_scores"] = scores
    report["rubric_categories"] = rubric_categories_from_scores(scores)
    scored = [row for row in scores if row.get("score") is not None]
    report["rubric_overall"] = round(sum(int(row["score"]) for row in scored) / len(scored)) if scored else 0
    if not report.get("dimensions"):
        report["dimensions"] = legacy_dimensions_from_rubric(scores)
    if not substantive:
        report["overall_score"] = 0
    elif report.get("overall_score") is None:
        report["overall_score"] = report["rubric_overall"]
    return report


def _report(db: Session, user: User, session: LiveInterviewSession) -> dict:
    from backend.app.services.mock_interview_prompts import feedback_system_prompt, feedback_user_prompt

    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    description = ""
    if isinstance(session.feedback, dict):
        description = str(session.feedback.get("job_description") or "")
    lines = []
    candidate_turns = 0
    for turn in session.transcript or []:
        role = turn.get("role")
        if role == "suggestion":
            continue
        if role == "candidate":
            candidate_turns += 1
            lines.append(f"Candidate: {turn.get('text')}")
        elif role == "interviewer":
            lines.append(f"Interviewer: {turn.get('text')}")
    context = _profile_brief(user, profile, session.job_title, session.company, description)
    system = (
        "This is a live job interview, not a practice chat. Score only what the candidate said aloud. "
        "Ignore any coach text.\n"
        + feedback_system_prompt(context=context, types=["behavioral", "technical", "hr"])
    )
    user_prompt = feedback_user_prompt("\n".join(lines) or "(empty)", candidate_turns=candidate_turns)
    raw = complete(
        db, AiTask.MOCK_INTERVIEW_FEEDBACK, system=system, user=user_prompt,
        feature=_feature(db), temperature=0.1, max_tokens=12000,
    )
    report = _parse_feedback(raw)
    substantive = candidate_turns > 0 and any(
        len(str(turn.get("text") or "").split()) >= 8
        for turn in (session.transcript or [])
        if turn.get("role") == "candidate"
    )
    if candidate_turns == 0:
        report["summary"] = report["summary"] or "No spoken answers were captured from the candidate."
    return _apply_mock_rubric(report, substantive=substantive)


def end_session(db: Session, user: User, session_id: uuid.UUID) -> dict:
    session = db.get(LiveInterviewSession, session_id)
    if session is None or session.user_id != user.id:
        raise AppError("NOT_FOUND", "That interview was not found.", 404)
    token = db.get(LiveInterviewToken, session.token_id)
    if session.status != "completed":
        kept = session.feedback if isinstance(session.feedback, dict) else {}
        try:
            _ai_ready(db)
            report = _report(db, user, session)
        except AppError as exc:
            report = _apply_mock_rubric({
                "overall_score": 0,
                "summary": exc.message,
                "knowledge_summary": exc.message,
                "dimensions": [],
                "strengths": [],
                "suggestions": [],
                "sample_answers": [],
                "question_breakdown": [],
                "rubric_scores": [],
            }, substantive=False, empty_note=exc.message)
        if kept.get("job_description"):
            report["job_description"] = kept["job_description"]
        session.feedback = report
        session.status = "completed"
        session.ended_at = _now()
        if token is not None:
            token.status = "used"
    code = token.code if token is not None else ""
    return session_out(session, token_code=code)


def list_sessions(db: Session, user_id: uuid.UUID) -> list[dict]:
    rows = db.scalars(
        select(LiveInterviewSession)
        .where(LiveInterviewSession.user_id == user_id)
        .order_by(LiveInterviewSession.created_at.desc())
        .limit(50)
    ).all()
    return [session_out(s) for s in rows]


def _job_for_application(db: Session, user_id: uuid.UUID, application_id: uuid.UUID) -> tuple[Application, Job]:
    app = db.get(Application, application_id)
    if app is None or app.user_id != user_id:
        raise AppError("NOT_FOUND", "That application was not found.", 404)
    job = db.get(Job, app.job_id)
    if job is None:
        raise AppError("NOT_FOUND", "That job was not found.", 404)
    return app, job


def attach_application(db: Session, user: User, session_id: uuid.UUID, application_id: uuid.UUID) -> dict:
    session = db.get(LiveInterviewSession, session_id)
    if session is None or session.user_id != user.id:
        raise AppError("NOT_FOUND", "That interview was not found.", 404)
    app, job = _job_for_application(db, user.id, application_id)
    session.application_id = app.id
    session.job_title = job.title
    session.company = job.company
    feedback = dict(session.feedback) if isinstance(session.feedback, dict) else {}
    if job.description:
        feedback["job_description"] = (job.description or "")[:4000]
    session.feedback = feedback or None
    token = db.get(LiveInterviewToken, session.token_id)
    return session_out(session, token_code=token.code if token else "")


def regenerate_report(db: Session, user: User, session_id: uuid.UUID) -> dict:
    session = db.get(LiveInterviewSession, session_id)
    if session is None or session.user_id != user.id:
        raise AppError("NOT_FOUND", "That interview was not found.", 404)
    if session.status != "completed":
        raise AppError("SESSION_OPEN", "End the interview in the desktop agent before regenerating the report.", 409)
    _ai_ready(db)
    kept = session.feedback if isinstance(session.feedback, dict) else {}
    report = _report(db, user, session)
    if kept.get("job_description"):
        report["job_description"] = kept["job_description"]
    session.feedback = report
    token = db.get(LiveInterviewToken, session.token_id)
    return session_out(session, token_code=token.code if token else "")


def get_session(db: Session, user_id: uuid.UUID, session_id: uuid.UUID) -> dict:
    session = db.get(LiveInterviewSession, session_id)
    if session is None or session.user_id != user_id:
        raise AppError("NOT_FOUND", "That interview was not found.", 404)
    token = db.get(LiveInterviewToken, session.token_id)
    return session_out(session, token_code=token.code if token else "")


def admin_sessions(db: Session) -> list[dict]:
    rows = db.execute(
        select(LiveInterviewSession, User, LiveInterviewToken)
        .join(User, User.id == LiveInterviewSession.user_id)
        .join(LiveInterviewToken, LiveInterviewToken.id == LiveInterviewSession.token_id)
        .order_by(LiveInterviewSession.created_at.desc())
        .limit(100)
    ).all()
    out = []
    for session, user, token in rows:
        item = session_out(session, token_code=token.code)
        item["email"] = user.email
        item["token_status"] = token.status
        out.append(item)
    return out
