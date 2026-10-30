"""CRUD for custom (non-profile) application questions."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.app.core.errors import AppError
from backend.app.schemas.application_preferences import HumanQuestionIn
from backend.app.services.ai_service import AiTask, ai_available, complete
from backend.app.services.master_profile_service import _is_standard_human_pattern, ensure_master_data
from backend.app.services.preferences_service import _application_row, _validate_human_questions

_INVENTED_CLAIM_RE = re.compile(
    r"\b(devops|devlops|kubernetes|kubernet|\baws\b|techglora)\b",
    re.I,
)
_PLACEHOLDER_ANSWERS = {
    "",
    "- select an option",
    "select an option",
    "select",
    "n/a",
    "na",
    "unknown",
    "i prefer not to guess",
    "i prefer not to guess.",
}
_DENY_LABELS = ("gender", "race", "ethnicity", "disability", "veteran", "sexual")
_PREFERENCE_RE = re.compile(r"\b(comfortable|willing|agree to|okay with|open to a long-term)\b", re.I)
_AI_BATCH = 8
_AI_MAX = 40


def _normalize_row(row: dict) -> dict:
    pattern = str(row.get("pattern") or "").strip()
    out = HumanQuestionIn.model_validate(row).model_dump()
    out["normalized_pattern"] = pattern.lower()
    out.setdefault("verified", bool(row.get("verified")))
    out.setdefault("usage_count", int(row.get("usage_count") or 0))
    out.setdefault("input_type", (row.get("field_types") or ["text"])[0])
    out.setdefault("company", str(row.get("company") or "")[:200])
    out.setdefault("job_title", str(row.get("job_title") or "")[:200])
    out.setdefault("created_at", row.get("created_at") or datetime.now(timezone.utc).isoformat())
    out.setdefault("updated_at", row.get("updated_at"))
    out.setdefault("last_used_at", row.get("last_used_at"))
    return out


def _row_score(row: dict) -> int:
    score = int(row.get("usage_count") or 0) * 10
    if row.get("verified"):
        score += 50
    if str(row.get("answer") or "").strip():
        score += 5
    return score


def _dedupe_rows(rows: list) -> list[dict]:
    by_pattern: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            norm = _normalize_row(row)
        except Exception:
            continue
        key = str(norm.get("normalized_pattern") or "").strip()
        if not key:
            continue
        prev = by_pattern.get(key)
        if prev is None:
            by_pattern[key] = norm
            continue
        winner = norm if _row_score(norm) > _row_score(prev) else prev
        other = prev if winner is norm else norm
        winner["usage_count"] = max(int(prev.get("usage_count") or 0), int(norm.get("usage_count") or 0))
        winner["verified"] = bool(prev.get("verified") or norm.get("verified"))
        if not str(winner.get("answer") or "").strip():
            winner["answer"] = other.get("answer") or winner.get("answer")
        by_pattern[key] = winner
    return list(by_pattern.values())


def _years_label(value) -> str:
    try:
        years = int(value or 0)
    except (TypeError, ValueError):
        years = 0
    if years <= 0:
        return "0 years"
    if years == 1:
        return "1 year"
    return f"{years} years"


def _months_label(value) -> str:
    try:
        months = int(value or 0)
    except (TypeError, ValueError):
        months = 0
    if months <= 0:
        return "0 months"
    if months == 1:
        return "1 month"
    return f"{months} months"


def _first_education(profile) -> dict:
    for row in (profile.education if profile else None) or []:
        if isinstance(row, dict):
            return row
    return {}


def _role_title(profile) -> str:
    headline = str((profile.headline if profile else "") or "").split("|")[0].strip()
    title = str((profile.current_title if profile else "") or "").strip()
    blob = f"{headline} {title} {' '.join(list(profile.skills or []) if profile else [])} {(profile.summary if profile else '')}".lower()
    if "servicenow" in blob:
        if headline and "servicenow" in headline.lower():
            return headline.split("·")[0].strip()[:200]
        return "ServiceNow Administrator"
    return (headline or title)[:200]


def _heuristic_answer(pattern: str, *, profile, master: dict) -> str | None:
    low = (pattern or "").lower().strip()
    professional = master.get("professional") if isinstance(master.get("professional"), dict) else {}
    personal = master.get("personal") if isinstance(master.get("personal"), dict) else {}
    edu = _first_education(profile)
    years = profile.experience_years if profile else None
    months = professional.get("additional_months")
    status = str(professional.get("employment_status") or "").lower()
    fresher = status == "fresher" or (years is not None and int(years) <= 0)

    if "additional months" in low or re.search(r"months of experience", low):
        return _months_label(months)
    if re.search(r"years of (professional )?experience|total years of", low):
        return _years_label(years)
    if low in {"company", "current company", "employer", "current employer"}:
        company = str((profile.current_company if profile else "") or "").strip()
        if fresher or not company:
            return "Not applicable"
        return company[:200]
    if low in {"your title", "title", "current title", "job title"}:
        return _role_title(profile) or "Not applicable"
    if low in {"description"} or "relevant experience" in low:
        summary = str((profile.summary if profile else "") or "").strip()
        return summary[:2000] if summary else None
    if low in {"degree"}:
        return str(edu.get("degree") or "").strip()[:200] or None
    if low in {"school"}:
        school = str(edu.get("school") or "").strip()
        return school[:200] or None
    if "major" in low or "field of study" in low or "stream of study" in low:
        field = str(edu.get("field") or edu.get("degree") or "").strip()
        return field[:200] or None
    if "year" in low and ("graduat" in low or "complete" in low) and "experience" not in low:
        year = str(edu.get("end_year") or "").strip()
        return year or None
    if "highest level of education" in low:
        degree = str(edu.get("degree") or "").lower()
        if "mca" in degree or "master" in degree:
            return "Master's / post-graduation"
        if degree:
            return str(edu.get("degree")).strip()[:200]
        return None
    if "gender" in low:
        gender = str(personal.get("gender") or "").strip()
        return gender or None
    if "whom do you know" in low or "do you know anyone" in low:
        return "No" if "do you know anyone" in low else "Not applicable"
    return None


def _needs_ai_rewrite(pattern: str, answer: str, *, fresher: bool = False) -> bool:
    text = f"{pattern} {answer}"
    if _INVENTED_CLAIM_RE.search(text or ""):
        return True
    if (answer or "").strip().lower() in _PLACEHOLDER_ANSWERS:
        return True
    if re.search(r"\b1 year of experience\b", answer or "", re.I):
        return True
    if (answer or "").strip() in {"0", "0.0"} and re.search(r"\b(cgpa|cpi|gpa|percentage|score)\b", pattern or "", re.I):
        return True
    if fresher and (answer or "").strip().lower() == "yes" and re.search(
        r"production|shipped react|typescript on both|early-stage startup",
        pattern or "",
        re.I,
    ):
        return True
    return False


def _denied_label(pattern: str) -> bool:
    low = (pattern or "").lower()
    return any(token in low for token in _DENY_LABELS)


def _should_ai_fill(row: dict, *, fresher: bool) -> bool:
    if row.get("verified"):
        return False
    pattern = str(row.get("pattern") or "")
    answer = str(row.get("answer") or "").strip()
    if not pattern or _denied_label(pattern):
        return False
    if answer.lower() in {"yes", "no", "not applicable"}:
        if _needs_ai_rewrite(pattern, answer, fresher=fresher):
            return True
        return False
    if _needs_ai_rewrite(pattern, answer, fresher=fresher):
        return True
    if _PREFERENCE_RE.search(pattern):
        return False
    return True


def _normalize_ai_answer(pattern: str, answer: str) -> str:
    text = re.sub(r"\s+", " ", (answer or "")).strip()
    if not text:
        return ""
    yes_no_question = bool(re.match(r"^(have you|do you|are you|did you|can you|will you)\b", pattern or "", re.I))
    if yes_no_question and re.search(r"prefer not to guess", text, re.I):
        return "No"
    return text


def _parse_json_object(raw: str) -> dict:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AppError("AI_PARSE_ERROR", "Could not parse AI custom-question answers.", 502) from exc
    return data if isinstance(data, dict) else {}


def _llm_fill_answers(db: Session, *, context: str, questions: list[dict]) -> dict[str, str]:
    payload = {
        "candidate_context": (context or "")[:9000],
        "questions": [{"id": q["id"], "question": q["question"]} for q in questions],
    }
    system = (
        "Answer job-application screening questions for this candidate. Output ONLY JSON "
        "mapping each question id to an answer string. "
        "Use only the resume and profile in candidate_context. "
        "Do not invent employers, job titles, tools, cloud platforms, degrees, dates, salary, "
        "or production experience. If they are a fresher with no employer, do not name a company. "
        "Yes/no skill or experience questions: Yes only when the context supports it, otherwise No. "
        "If a fact is not in the context, answer 'I prefer not to guess'. "
        "Keep answers short: Yes, No, a number, or 1-3 sentences."
    )
    raw = complete(
        db,
        AiTask.APP_ANSWER,
        system=system,
        user=json.dumps(payload, ensure_ascii=False)[:12000],
        feature="applications",
        temperature=0.2,
        max_tokens=1800,
    )
    data = _parse_json_object(raw)
    allowed = {str(q["id"]) for q in questions}
    out: dict[str, str] = {}
    for key, value in data.items():
        if str(key) not in allowed:
            continue
        text = re.sub(r"\s+", " ", str(value or "")).strip()[:2000]
        if text:
            out[str(key)] = text
    return out


def list_custom_questions(db: Session, user) -> dict:
    prefs = _application_row(db, user)
    items = []
    for row in _dedupe_rows(prefs.human_questions or []):
        pattern = str(row.get("pattern") or "")
        if _is_standard_human_pattern(pattern):
            continue
        items.append(row)
    return {"items": items, "total": len(items)}


def replace_custom_questions(db: Session, user, items: list) -> dict:
    for row in items:
        if not isinstance(row, dict):
            raise ValueError("Each question must be an object")
    cleaned = [
        row
        for row in _dedupe_rows(items)
        if not _is_standard_human_pattern(str(row.get("pattern") or ""))
    ]
    prefs = _application_row(db, user)
    prefs.human_questions = _validate_human_questions(cleaned)
    flag_modified(prefs, "human_questions")
    db.commit()
    return list_custom_questions(db, user)


def sync_custom_questions_from_profile(db: Session, user) -> dict:
    """Dedupe, drop Master Profile fields, and fill answers from the resume with AI."""
    if user.profile is None:
        raise AppError("VALIDATION_ERROR", "Create a profile first.", 422)
    profile = user.profile
    master = ensure_master_data(profile)
    prefs = _application_row(db, user)
    original_count = len([r for r in (prefs.human_questions or []) if isinstance(r, dict)])
    rows = _dedupe_rows(prefs.human_questions or [])
    dropped_standard: list[str] = []
    updated: list[str] = []
    kept: list[dict] = []
    status = str((master.get("professional") or {}).get("employment_status") or "").lower()
    fresher = status == "fresher" or (profile.experience_years is not None and int(profile.experience_years) <= 0)

    for row in rows:
        pattern = str(row.get("pattern") or "")
        if _is_standard_human_pattern(pattern):
            dropped_standard.append(pattern)
            continue
        if not row.get("verified"):
            guessed = _heuristic_answer(pattern, profile=profile, master=master)
            if guessed and guessed != str(row.get("answer") or ""):
                row = {**row, "answer": guessed[:2000], "updated_at": datetime.now(timezone.utc).isoformat()}
                updated.append(pattern)
        kept.append(row)

    source = "heuristic"
    if ai_available(db, feature="applications") or ai_available(db, feature="resume"):
        from backend.app.services import application_context

        targets = [row for row in kept if _should_ai_fill(row, fresher=fresher)][:_AI_MAX]
        if targets:
            try:
                ctx = application_context.build_context(db, user.id, include_default_resume=True)
            except Exception:
                ctx = ""
            if ctx:
                by_id = {str(row.get("id") or ""): row for row in targets if row.get("id")}
                ids = list(by_id.keys())
                for i in range(0, len(ids), _AI_BATCH):
                    batch = ids[i : i + _AI_BATCH]
                    questions = [{"id": qid, "question": str(by_id[qid].get("pattern") or "")} for qid in batch]
                    try:
                        filled = _llm_fill_answers(db, context=ctx, questions=questions)
                    except AppError:
                        continue
                    for qid, answer in filled.items():
                        row = by_id.get(qid)
                        if not row:
                            continue
                        answer = _normalize_ai_answer(str(row.get("pattern") or ""), answer)
                        if not answer or answer == str(row.get("answer") or ""):
                            continue
                        row["answer"] = answer[:2000]
                        row["updated_at"] = datetime.now(timezone.utc).isoformat()
                        updated.append(str(row.get("pattern") or ""))
                        source = "ai"

    prefs.human_questions = _validate_human_questions(kept)
    flag_modified(prefs, "human_questions")
    db.commit()
    listed = list_custom_questions(db, user)
    return {
        "source": source,
        "updated": list(dict.fromkeys(updated)),
        "dropped_standard": dropped_standard,
        "deduped_from": original_count,
        **listed,
    }


def _find_question(prefs, question_id: str) -> tuple[list, int]:
    human = list(prefs.human_questions or [])
    for i, row in enumerate(human):
        if str(row.get("id") or "") == question_id:
            return human, i
    raise LookupError(question_id)


def update_custom_question(db: Session, user, question_id: str, patch: dict) -> dict:
    prefs = _application_row(db, user)
    human, idx = _find_question(prefs, question_id)
    row = dict(human[idx])
    row.update({k: v for k, v in patch.items() if k != "id"})
    row["updated_at"] = datetime.now(timezone.utc).isoformat()
    human[idx] = _normalize_row(row)
    prefs.human_questions = _validate_human_questions(human)
    db.commit()
    return _normalize_row(human[idx])


def delete_custom_question(db: Session, user, question_id: str) -> None:
    prefs = _application_row(db, user)
    human, idx = _find_question(prefs, question_id)
    human.pop(idx)
    prefs.human_questions = human
    db.commit()


def touch_question_usage(human_questions: list, label: str) -> bool:
    """Increment usage when a custom rule matches (called from ingest when possible)."""
    from automation.qa_resolver import match_human_custom

    ans = match_human_custom(label, human_questions)
    if not ans:
        return False
    lower = (label or "").strip().lower()
    changed = False
    for row in human_questions:
        if not isinstance(row, dict):
            continue
        pattern = str(row.get("pattern") or "").strip().lower()
        match = (row.get("match") or "contains").lower()
        hit = match == "exact" and lower == pattern or match != "exact" and pattern in lower
        if hit:
            row["usage_count"] = int(row.get("usage_count") or 0) + 1
            row["last_used_at"] = datetime.now(timezone.utc).isoformat()
            changed = True
            break
    return changed
