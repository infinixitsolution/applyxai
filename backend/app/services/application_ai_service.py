"""Platform AI helpers for job application form questions."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from automation.answer_format import infer_answer_format, normalize_numeric_answer
from automation.qa_resolver import can_use_ai

from backend.app.core.errors import AppError
from backend.app.models import User
from backend.app.services import application_context, preferences_service
from backend.app.services.ai_service import AiTask, ai_available, complete


def _ai_feature(db: Session) -> str:
    if ai_available(db, feature="applications"):
        return "applications"
    if ai_available(db, feature="resume"):
        return "resume"
    return ""


def answer_application_question(
    db: Session,
    user_id: uuid.UUID,
    *,
    question: str,
    question_type: str = "text",
    options: list[str] | None = None,
    job_description: str = "",
    job_title: str = "",
    company: str = "",
) -> str:
    """Answer one screening question using profile, preferences, and default resume text."""
    feature = _ai_feature(db)
    if not feature:
        raise AppError("AI_DISABLED", "Platform AI is not enabled for applications.", 503)
    user = db.get(User, user_id)
    if user is None:
        raise AppError("NOT_FOUND", "User not found", 404)
    doc = preferences_service.application_document(db, user)
    deny = (doc.get("ai_policy") or {}).get("deny_label_contains") or []
    label = (question or "").lower()
    if any(d and d in label for d in deny):
        raise AppError("AI_DENIED", "This question is not eligible for AI answers.", 403)
    qtype = (question_type or "text").lower()
    if qtype not in ("text", "textarea", "select", "radio", "number", "tel"):
        raise AppError("VALIDATION", "Unsupported question type.", 422)
    answer_fmt = infer_answer_format(question, qtype)
    ai_qtype = "number" if answer_fmt == "number" else qtype
    if not can_use_ai(label, ai_qtype if ai_qtype != "tel" else "number", doc.get("ai_policy") or {}):
        raise AppError("AI_DENIED", "This question is not eligible for AI answers.", 403)
    ctx = application_context.build_context(
        db,
        user_id,
        job_description=job_description,
        job_title=job_title,
        company=company,
        include_default_resume=True,
    )
    system = (
        "You help fill job application forms. Answer briefly and truthfully using only the candidate context. "
        "Do not invent credentials, employers, or legal status. If unsure, say you prefer not to guess."
    )
    if qtype in ("select", "radio") and options:
        opts = "\n".join(f"- {o}" for o in options[:40])
        user_prompt = (
            f"Context:\n{ctx}\n\nQuestion: {question}\n\n"
            f"Pick exactly one option (copy the option text verbatim):\n{opts}"
        )
        task = AiTask.APP_ANSWER_SELECT
    elif answer_fmt == "number":
        user_prompt = (
            f"Context:\n{ctx}\n\nQuestion: {question}\n\n"
            "This field accepts numbers only (for example years, salary amount, or notice period in days). "
            "Reply with digits only — no words, units, sentences, or punctuation."
        )
        task = AiTask.APP_ANSWER
    else:
        user_prompt = f"Context:\n{ctx}\n\nQuestion ({qtype}): {question}\n\nAnswer:"
        task = AiTask.APP_ANSWER
    raw = (complete(db, task, system=system, user=user_prompt, feature=feature, max_tokens=800) or "").strip()
    if answer_fmt == "number":
        return normalize_numeric_answer(question, raw)
    return raw
