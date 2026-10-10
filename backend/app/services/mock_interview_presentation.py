"""Video presentation and answer-authenticity analysis for mock interviews."""

from __future__ import annotations

import base64
import json
import re

from sqlalchemy.orm import Session

from backend.app.models import MockInterviewSession
from backend.app.models.enums import MockInterviewMessageRole
from backend.app.services import ai_service
from backend.app.services.ai_service import AiTask
from backend.app.services.mock_interview_behavior_parameters import (
    BEHAVIOR_ANALYSIS_VERSION,
    behavior_categories_from_scores,
    behavior_prompt_catalog,
    conduct_issues_from_behavior,
    normalize_behavior_scores,
)

_FEATURE = "mock_interview"
_MAX_FRAME_BYTES = 450_000
_MAX_FRAMES = 12

# Rubric parameter id for interview conduct (professional_etiquette).
_PROFESSIONAL_ETIQUETTE_ID = 74

CONDUCT_ISSUE_LABELS: dict[str, str] = {
    "smoking": "Smoking visible on camera",
    "vaping": "Vaping visible on camera",
    "eating": "Eating during the interview",
    "drinking_alcohol": "Alcoholic drink visible",
    "phone_use": "Using phone during the interview",
    "inappropriate_background": "Distracting or unprofessional background",
    "off_camera_behavior": "Other unprofessional on-camera behavior",
}

BOOKISH_PATTERNS = [
    r"\b furthermore\b",
    r"\b moreover\b",
    r"\b consequently\b",
    r"\b it is imperative\b",
    r"\b leverage synergies\b",
    r"\b paradigm\b",
    r"\b holistic approach\b",
    r"\b as per my understanding\b",
    r"\b in today's dynamic landscape\b",
]

AI_LIKE_PATTERNS = [
    r"\b as an ai language model\b",
    r"\b i'd be happy to help\b",
    r"\b certainly!?\b",
    r"\b great question!?\b",
    r"\b in conclusion,?\s",
    r"\b to summarize,?\s",
    r"\b here are (?:three|several) (?:key )?points\b",
]

HUMAN_SIGNALS = [
    r"\b(i think|i guess|honestly|basically|actually|um|uh|you know)\b",
    r"\b(last year|months ago|at my (?:last|previous) (?:job|company))\b",
    r"\bwe (?:shipped|built|fixed|launched)\b",
]


def _normalize_frame_data_url(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty frame")
    if text.startswith("data:"):
        if ";base64," not in text:
            raise ValueError("invalid data url")
        return text
    base64.b64decode(text[:200] + "==", validate=False)
    return f"data:image/jpeg;base64,{text}"


def validate_presentation_frames(frames: list[str] | None) -> list[str]:
    if not frames:
        return []
    out: list[str] = []
    for raw in frames[:_MAX_FRAMES]:
        url = _normalize_frame_data_url(raw)
        b64 = url.split(",", 1)[-1]
        if len(base64.b64decode(b64)) > _MAX_FRAME_BYTES:
            continue
        out.append(url)
    return out


def _parse_json_object(raw: str) -> dict:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("not an object")
    return data


def analyze_presentation_frames(db: Session, frames: list[str]) -> dict:
    if not frames:
        return {
            "available": False,
            "reason": "no_frames",
            "presentability_summary": "No camera snapshots were captured for visual assessment.",
        }
    if not ai_service.ai_available(db, feature=_FEATURE):
        return {"available": False, "reason": "ai_disabled"}

    catalog = behavior_prompt_catalog()
    system = (
        "You assess mock interview JPEG snapshots for on-camera behavioral analysis and professional presentability. "
        "Infer ONLY what is clearly visible across the stills. Be respectful—coaching, not appearance judgment.\n"
        "Parameters marked [audio] cannot be verified from stills alone—use status not_observable. "
        "[video_limited] params may only be partially inferred.\n"
        "Output ONLY JSON:\n"
        "{\n"
        '  "overall_score": 0-100,\n'
        '  "facial_expression": {"score": 0-100, "notes": "summary of params 6-10"},\n'
        '  "eye_contact": {"score": 0-100, "notes": "summary of params 1-5"},\n'
        '  "grooming": {"score": 0-100, "notes": "attire/neatness visible on camera"},\n'
        '  "professional_conduct": {"score": 0-100, "issues": [], "notes": "prohibited activity summary"},\n'
        '  "behavioral_parameters": [\n'
        '    {"id": 1, "score": 0-100 or null, "status": "ok|concern|not_observable|na", "detected": false, "notes": "brief evidence"}\n'
        "  ],\n"
        '  "presentability_summary": "2-3 sentences of constructive coaching"\n'
        "}\n"
        "You MUST return behavioral_parameters with an entry for every parameter id 1 through 55.\n"
        "status=concern and detected=true when the criteria clearly apply (especially prohibited activities). "
        "For smoking/vape/cigarette in ANY frame: id 26 smoking_detection must be concern, detected=true, score<=25.\n"
        "professional_conduct.issues tokens: smoking, vaping, eating, drinking_alcohol, phone_use, "
        "inappropriate_background, off_camera_behavior.\n"
        "Parameter catalog:\n"
        f"{catalog}"
    )
    content: list[dict] = [
        {"type": "text", "text": f"Assess these {len(frames)} snapshot(s) from a mock video interview."}
    ]
    detail = "high" if len(frames) <= 8 else "auto"
    for url in frames:
        content.append({"type": "image_url", "image_url": {"url": url, "detail": detail}})

    raw = ai_service.complete_messages(
        db,
        AiTask.MOCK_INTERVIEW_FEEDBACK,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": content}],
        feature=_FEATURE,
        temperature=0.15,
        max_tokens=8000,
    )
    data = _parse_json_object(raw)
    _normalize_presentation_payload(data)
    data["available"] = True
    return data


def _normalize_conduct_issues(raw_issues: list | str) -> list[str]:
    if isinstance(raw_issues, str):
        raw_issues = [raw_issues]
    issues: list[str] = []
    for item in raw_issues or []:
        token = str(item).lower().strip().replace(" ", "_").replace("-", "_")
        if token in ("cigarette", "cigar", "cigarettes", "smoke", "hookah"):
            token = "smoking"
        if token in ("e_cigarette", "ecig", "juul"):
            token = "vaping"
        if token and token not in issues:
            issues.append(token)
    return issues


def _normalize_presentation_payload(data: dict) -> None:
    scores = normalize_behavior_scores(data.get("behavioral_parameters"))
    data["behavior_analysis_version"] = BEHAVIOR_ANALYSIS_VERSION
    data["behavioral_parameters"] = scores
    data["behavior_categories"] = behavior_categories_from_scores(scores)
    scored = [r for r in scores if r.get("score") is not None]
    if scored:
        data["behavior_overall"] = round(sum(int(r["score"]) for r in scored) / len(scored))
    else:
        data["behavior_overall"] = None

    pc = data.get("professional_conduct")
    if not isinstance(pc, dict):
        pc = {"score": None, "issues": [], "notes": ""}
        data["professional_conduct"] = pc
    issues = _normalize_conduct_issues(pc.get("issues") or [])
    for code in conduct_issues_from_behavior(scores):
        if code not in issues:
            issues.append(code)
    pc["issues"] = issues
    try:
        pc["score"] = int(pc["score"]) if pc.get("score") is not None else None
    except (TypeError, ValueError):
        pc["score"] = None
    if issues and (pc["score"] is None or pc["score"] > 35):
        pc["score"] = 20 if "smoking" in issues or "vaping" in issues else 30


def merge_presentation_conduct_into_feedback(feedback: dict, presentation: dict) -> dict:
    """Lower scores and surface coaching when camera analysis flags conduct issues."""
    if not presentation.get("available"):
        return feedback
    pc = presentation.get("professional_conduct") or {}
    issues = list(pc.get("issues") or [])
    for code in conduct_issues_from_behavior(presentation.get("behavioral_parameters") or []):
        if code not in issues:
            issues.append(code)
    behavioral_concerns = [
        r
        for r in presentation.get("behavioral_parameters") or []
        if r.get("status") == "concern" or r.get("detected")
    ]
    if not issues and not behavioral_concerns:
        return feedback

    conduct_score = pc.get("score")
    if conduct_score is None:
        if issues:
            conduct_score = 20 if "smoking" in issues or "vaping" in issues else 35
        else:
            concern_scores = [int(r["score"]) for r in behavioral_concerns if r.get("score") is not None]
            conduct_score = min(concern_scores) if concern_scores else 40
    conduct_score = max(0, min(100, int(conduct_score)))

    if presentation.get("overall_score") is not None:
        presentation["overall_score"] = min(int(presentation["overall_score"]), conduct_score)

    for row in feedback.get("rubric_scores") or []:
        if row.get("id") == _PROFESSIONAL_ETIQUETTE_ID or row.get("key") == "professional_etiquette":
            prev = row.get("score")
            row["score"] = conduct_score if prev is None else min(int(prev), conduct_score)
            conduct_note = pc.get("notes") or ""
            concern_labels = [r.get("label", "") for r in behavioral_concerns[:5] if r.get("label")]
            issue_text = ", ".join(CONDUCT_ISSUE_LABELS.get(i, i.replace("_", " ")) for i in issues)
            if concern_labels and not issue_text:
                issue_text = ", ".join(concern_labels)
            extra = f"On-camera analysis: {issue_text}. {conduct_note}".strip()
            row["notes"] = f"{row.get('notes') or ''} {extra}".strip()

    improvements: list[str] = list(feedback.get("improvements") or [])
    for code in issues:
        label = CONDUCT_ISSUE_LABELS.get(code, code.replace("_", " "))
        tip = f"{label} — real interviews expect a smoke-free, focused on-camera environment."
        if tip not in improvements:
            improvements.insert(0, tip)
    for row in behavioral_concerns[:6]:
        if row.get("category_id") == "prohibited":
            continue
        tip = f"On-camera: {row.get('label')} — {row.get('notes') or 'see behavioral analysis report.'}"
        if tip not in improvements:
            improvements.append(tip)
    feedback["improvements"] = improvements[:16]

    summary = (feedback.get("knowledge_summary") or "").strip()
    flag = "On-camera conduct issues were detected (see presentation section)."
    if flag not in summary:
        feedback["knowledge_summary"] = f"{flag} {summary}".strip() if summary else flag

    if feedback.get("rubric_scores"):
        scored = [r for r in feedback["rubric_scores"] if r.get("score") is not None]
        if scored:
            feedback["rubric_overall"] = round(sum(int(r["score"]) for r in scored) / len(scored))
            if scored[0].get("category_id"):
                from backend.app.services.mock_interview_rubric import rubric_categories_from_scores

                feedback["rubric_categories"] = rubric_categories_from_scores(feedback["rubric_scores"])

    return feedback


def _heuristic_authenticity(session: MockInterviewSession) -> dict:
    texts = [m.content for m in (session.messages or []) if m.role == MockInterviewMessageRole.CANDIDATE]
    combined = " ".join(texts).lower()
    if not combined.strip():
        return {"overall": "missing", "confidence": 95, "signals": ["No candidate speech in transcript."]}

    bookish = sum(1 for p in BOOKISH_PATTERNS if re.search(p, combined, re.I))
    ai_like = sum(1 for p in AI_LIKE_PATTERNS if re.search(p, combined, re.I))
    human = sum(1 for p in HUMAN_SIGNALS if re.search(p, combined, re.I))

    signals: list[str] = []
    if bookish >= 2:
        signals.append("Formal or textbook-style phrasing detected.")
    if ai_like >= 1:
        signals.append("Generic assistant-like phrasing detected.")
    if human >= 2:
        signals.append("Natural conversational markers and personal timeline references.")

    if ai_like >= 2:
        overall = "ai_like"
    elif bookish >= 2 and human == 0:
        overall = "bookish"
    elif human >= 1 and bookish <= 1:
        overall = "human"
    else:
        overall = "mixed"

    return {"overall": overall, "confidence": min(95, 40 + human * 15 + bookish * 10), "signals": signals}


def analyze_answer_authenticity(db: Session, session: MockInterviewSession, transcript: str) -> dict:
    base = _heuristic_authenticity(session)
    if not ai_service.ai_available(db, feature=_FEATURE):
        base["notes"] = "AI authenticity review unavailable."
        return base

    system = (
        "You judge whether mock interview answers sound spontaneously spoken by a real candidate vs rehearsed textbook "
        "answers vs AI-generated text. Use ONLY the transcript. Output ONLY JSON:\n"
        "{\n"
        '  "overall": "human|mixed|bookish|ai_like",\n'
        '  "confidence": 0-100,\n'
        '  "signals": ["short evidence bullets"],\n'
        '  "notes": "2-3 sentences for the candidate"\n'
        "}\n"
        "human: specific stories, imperfect grammar ok, personal details. bookish: jargon-heavy, essay-like, no personal anchor. "
        "ai_like: bullet templates, disclaimers, overly polished generic structure."
    )
    raw = ai_service.complete_messages(
        db,
        AiTask.MOCK_INTERVIEW_FEEDBACK,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Transcript:\n{transcript}"},
        ],
        feature=_FEATURE,
        temperature=0.1,
        max_tokens=900,
    )
    try:
        ai = _parse_json_object(raw)
    except (json.JSONDecodeError, ValueError):
        ai = {}
    merged = {**base, **{k: v for k, v in ai.items() if v is not None}}
    if base.get("signals") and ai.get("signals"):
        merged["signals"] = list(dict.fromkeys([*base["signals"], *ai["signals"]]))[:8]
    return merged
