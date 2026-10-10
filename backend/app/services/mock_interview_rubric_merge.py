"""Merge and calibrate 100-parameter rubric scores into feedback payloads."""

from __future__ import annotations

from backend.app.models import MockInterviewSession
from backend.app.services.mock_interview_feedback import _candidate_messages, _is_substantive
from backend.app.services.mock_interview_rubric import (
    RUBRIC_VERSION,
    empty_rubric_scores,
    legacy_dimensions_from_rubric,
    normalize_rubric_scores,
    rubric_categories_from_scores,
)


def apply_rubric_to_feedback(session: MockInterviewSession, feedback: dict) -> dict:
    raw = feedback.get("rubric_scores")
    scores = normalize_rubric_scores(raw if isinstance(raw, list) else None)
    scores = _calibrate_rubric(session, scores)
    feedback["rubric_version"] = RUBRIC_VERSION
    feedback["rubric_scores"] = scores
    feedback["rubric_categories"] = rubric_categories_from_scores(scores)
    scored = [r for r in scores if r.get("score") is not None]
    if scored:
        feedback["rubric_overall"] = round(sum(int(r["score"]) for r in scored) / len(scored))
    else:
        feedback["rubric_overall"] = 0
    if not feedback.get("dimensions"):
        feedback["dimensions"] = legacy_dimensions_from_rubric(scores)
    return feedback


def rubric_feedback_no_answers(session: MockInterviewSession) -> dict:
    scores = empty_rubric_scores(score=0, note="No candidate answers in transcript.")
    return {
        "rubric_version": RUBRIC_VERSION,
        "rubric_scores": scores,
        "rubric_categories": rubric_categories_from_scores(scores),
        "rubric_overall": 0,
    }


def _calibrate_rubric(session: MockInterviewSession, scores: list[dict]) -> list[dict]:
    candidates = _candidate_messages(session)
    substantive = [m for m in candidates if _is_substantive(m.content)]
    if not candidates or not substantive:
        return empty_rubric_scores(score=0, note="No meaningful candidate answers.")
    return scores
