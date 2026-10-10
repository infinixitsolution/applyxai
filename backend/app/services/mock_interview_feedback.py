"""Deterministic calibration so mock interview scores match transcript evidence."""

from __future__ import annotations

import re

from backend.app.models import MockInterviewMessage, MockInterviewSession
from backend.app.models.enums import MockInterviewMessageRole

DIMENSION_KEYS = ("communication", "technical", "behavioral", "role_fit")

FILLER_ONLY = re.compile(
    r"^(oral|um+|uh+|yes|no|okay|ok|hello|hi|thanks|thank you)[.!,\s]*$",
    re.I,
)

TECH_SIGNAL = re.compile(
    r"\b("
    r"python|java|javascript|typescript|react|node|api|aws|azure|gcp|docker|kubernetes|sql|"
    r"database|machine learning|ml|ai|llm|model|devops|ci/cd|git|cloud|engineer|developer|"
    r"backend|frontend|data|algorithm|system|deploy|server|code|programming|project|built|implemented"
    r")\b",
    re.I,
)

BEHAVIORAL_SIGNAL = re.compile(
    r"\b(when i|i led|i managed|i worked|my team|situation|challenge|result|because i|we delivered|star)\b",
    re.I,
)


def _candidate_messages(session: MockInterviewSession) -> list[MockInterviewMessage]:
    return [m for m in (session.messages or []) if m.role == MockInterviewMessageRole.CANDIDATE]


def _is_substantive(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 12:
        return False
    if FILLER_ONLY.match(t):
        return False
    return len(t.split()) >= 4


def _interviewer_questions(session: MockInterviewSession) -> list[str]:
    return [m.content.strip() for m in (session.messages or []) if m.role == MockInterviewMessageRole.INTERVIEWER and m.content.strip()]


def build_no_answer_feedback(session: MockInterviewSession) -> dict:
    questions = _interviewer_questions(session)
    breakdown = [
        {
            "question": q[:500],
            "answer_quality": "missing",
            "notes": "No candidate answer was recorded for this question.",
        }
        for q in questions
    ]
    dim_notes = {
        "communication": "No spoken answers were captured to assess communication.",
        "technical": "No technical explanation was provided by the candidate.",
        "behavioral": "No behavioral or STAR-style examples were shared.",
        "role_fit": "Role fit cannot be assessed without candidate responses.",
    }
    return {
        "overall_score": 0,
        "knowledge_summary": (
            "No meaningful candidate answers appear in the transcript. "
            "Scores are zero until you complete at least one full spoken answer during the interview."
        ),
        "dimensions": [
            {"key": k, "label": label, "score": 0, "notes": dim_notes[k]}
            for k, label in (
                ("communication", "Communication"),
                ("technical", "Technical depth"),
                ("behavioral", "Behavioral / STAR"),
                ("role_fit", "Role fit"),
            )
        ],
        "question_breakdown": breakdown,
        "strengths": [],
        "improvements": [
            "Allow the microphone and pause briefly after each answer so speech is transcribed.",
            "Answer at least the first question with a full 30–60 second response before ending the session.",
        ],
        "sample_answers": [],
    }


def _cap_from_breakdown(feedback: dict) -> int | None:
    breakdown = feedback.get("question_breakdown")
    if not isinstance(breakdown, list) or not breakdown:
        return None
    qualities = [str(q.get("answer_quality") or "").lower() for q in breakdown if isinstance(q, dict)]
    if not qualities:
        return None
    if all(q in ("missing", "weak") for q in qualities):
        return 10
    if not any(q in ("strong", "adequate") for q in qualities):
        return 15
    return None


def calibrate_feedback(session: MockInterviewSession, feedback: dict) -> dict:
    if feedback.get("error"):
        return feedback

    candidates = _candidate_messages(session)
    substantive = [m for m in candidates if _is_substantive(m.content)]
    combined = " ".join(m.content for m in candidates).strip()
    word_count = len(combined.split()) if combined else 0

    if not candidates or not substantive:
        return build_no_answer_feedback(session)

    breakdown_cap = _cap_from_breakdown(feedback)

    has_tech = bool(TECH_SIGNAL.search(combined))
    has_behavioral = bool(BEHAVIORAL_SIGNAL.search(combined))

    caps: dict[str, int] = dict.fromkeys(DIMENSION_KEYS, 100)

    if not has_tech:
        caps["technical"] = 8
    if not has_behavioral:
        caps["behavioral"] = 12 if word_count < 35 else 45

    if word_count < 8:
        for key in DIMENSION_KEYS:
            caps[key] = min(caps[key], 10)

    if breakdown_cap is not None:
        for key in DIMENSION_KEYS:
            caps[key] = min(caps[key], breakdown_cap)

    dims = feedback.get("dimensions")
    if not isinstance(dims, list):
        return feedback

    adjusted: list[int] = []
    for dim in dims:
        if not isinstance(dim, dict):
            continue
        key = str(dim.get("key") or "")
        try:
            raw = int(dim.get("score", 0))
        except (TypeError, ValueError):
            raw = 0
        cap = caps.get(key, 100)
        score = max(0, min(raw, cap))
        dim["score"] = score
        adjusted.append(score)
        if key == "technical" and not has_tech and score > 8:
            dim["notes"] = (
                (dim.get("notes") or "").strip()
                + " No substantive technical content appeared in the candidate's answers."
            ).strip()

    if adjusted:
        mean = round(sum(adjusted) / len(adjusted))
        try:
            overall = int(feedback.get("overall_score", mean))
        except (TypeError, ValueError):
            overall = mean
        feedback["overall_score"] = max(0, min(overall, mean, max(adjusted)))

    if not has_tech and isinstance(feedback.get("knowledge_summary"), str):
        if "technical" not in feedback["knowledge_summary"].lower():
            feedback["knowledge_summary"] = (
                feedback["knowledge_summary"].rstrip()
                + " The candidate did not demonstrate technical depth in their spoken answers."
            )

    return feedback
