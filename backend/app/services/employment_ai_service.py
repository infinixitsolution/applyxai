"""Fill employment from the resume, or mark Fresher when there are no employers."""

from __future__ import annotations

import copy
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.app.core.errors import AppError
from backend.app.models import ApplicationPreferences, User
from backend.app.services import master_profile_service, resume_service, resume_text_service, run_config_service
from backend.app.services.ai_service import AiTask, ai_available, complete

_SKIP_COMPANIES = {
    "",
    "na",
    "n/a",
    "none",
    "self",
    "fresher",
    "n.a",
    "not applicable",
    "student",
}


def _clip(text: str, *, limit: int) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())[:limit].rstrip()


def named_jobs(rows: list | None) -> list[dict]:
    """Keep only jobs with a real employer — never invent a company from a headline."""
    out: list[dict] = []
    seen: set[str] = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        company = _clip(str(row.get("company") or ""), limit=255)
        title = _clip(str(row.get("title") or ""), limit=255)
        if not company or company.lower() in _SKIP_COMPANIES:
            continue
        key = f"{company.lower()}|{title.lower()}"
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "title": title,
                "company": company,
                "location": _clip(str(row.get("location") or ""), limit=255),
                "start": _clip(str(row.get("start") or ""), limit=32),
                "end": _clip(str(row.get("end") or ""), limit=32),
                "summary": str(row.get("summary") or "").strip()[:2000],
            }
        )
    return out[:20]


def resume_says_fresher(resume_text: str) -> bool:
    blob = (resume_text or "").lower()
    if re.search(r"\bfresher\b", blob):
        return True
    if re.search(r"\bfirst\s+(full[- ]?time|professional)\s+role\b", blob):
        return True
    if re.search(r"\bno\s+(?:work|professional)\s+experience\b", blob):
        return True
    return False


def classify_employment(
    *,
    resume_text: str = "",
    work_history: list | None = None,
    experience_years: float | int | None = None,
) -> dict:
    jobs = named_jobs(work_history)
    fresher_word = resume_says_fresher(resume_text)
    years = None
    if experience_years is not None:
        try:
            years = float(experience_years)
        except (TypeError, ValueError):
            years = None
    if fresher_word or (not jobs and (years is None or years <= 1)):
        kind = "fresher"
        status = "Fresher"
        years_out = 0
        note = (
            "Resume has no employers. Marked as Fresher with 0 years of experience."
            if not jobs
            else "Resume lists internships or training. Marked as Fresher; jobs below are from the resume."
        )
    else:
        kind = "experienced"
        status = "Experienced"
        years_out = int(years) if years is not None else None
        note = f"{len(jobs)} job{'s' if len(jobs) != 1 else ''} from the resume."
    return {
        "kind": kind,
        "status": status,
        "jobs": jobs,
        "experience_years": years_out,
        "note": note,
    }


def _resume_text(db: Session, user_id) -> str:
    resume = run_config_service.default_resume(db, user_id)
    if resume is None:
        return ""
    try:
        path = resume_service.absolute_path(resume)
        text = resume_text_service.extract_text(path, resume.file_type)
    except OSError:
        return ""
    return (text or "").strip()


def _parse_json(raw: str) -> dict:
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
        raise AppError("AI_PARSE_ERROR", "Could not parse AI employment.", 502) from exc
    return data if isinstance(data, dict) else {}


def _llm_jobs(db: Session, *, resume_text: str) -> list[dict]:
    system = (
        "Extract paid jobs and internships from the resume. Output ONLY JSON "
        '{"jobs":[{"title","company","location","start","end","summary"}]}. '
        "Include a row only when a real employer/company name is present. "
        "Do not invent employers. Skip academic coursework unless it names an organization."
    )
    raw = complete(
        db,
        AiTask.APP_ANSWER,
        system=system,
        user=(resume_text or "")[:8000],
        feature="applications",
        temperature=0.1,
        max_tokens=800,
    )
    data = _parse_json(raw)
    return named_jobs(data.get("jobs") if isinstance(data.get("jobs"), list) else [])


def fill_employment_from_resume(db: Session, user: User) -> dict:
    if user.profile is None:
        raise AppError("VALIDATION_ERROR", "Create a profile first.", 422)
    profile = user.profile
    resume_text = _resume_text(db, user.id)
    parsed = resume_text_service.heuristic_profile_intake(resume_text) if resume_text else {}
    from_resume = named_jobs(parsed.get("work_history") if isinstance(parsed, dict) else [])
    source = "heuristic"
    if resume_text and not resume_says_fresher(resume_text) and (
        ai_available(db, feature="applications") or ai_available(db, feature="resume")
    ):
        try:
            ai_jobs = _llm_jobs(db, resume_text=resume_text)
            if ai_jobs:
                from_resume = named_jobs(ai_jobs + from_resume)
                source = "ai"
        except AppError:
            pass

    existing = named_jobs(list(profile.work_history or []))
    merged = named_jobs(from_resume + existing)
    guessed_years = parsed.get("experience_years") if isinstance(parsed, dict) else None
    classified = classify_employment(
        resume_text=resume_text,
        work_history=merged,
        experience_years=profile.experience_years if profile.experience_years is not None else guessed_years,
    )
    kind = classified["kind"]
    if kind == "fresher":
        profile.work_history = merged
        if profile.experience_years is None or int(profile.experience_years) <= 1:
            profile.experience_years = 0
        if not merged:
            profile.current_company = ""
    else:
        profile.work_history = merged
        if not profile.current_company and merged:
            profile.current_company = merged[0].get("company") or ""
        if profile.experience_years is None and classified.get("experience_years") is not None:
            profile.experience_years = classified["experience_years"]

    master = copy.deepcopy(master_profile_service.ensure_master_data(profile))
    professional = dict(master.get("professional") or {})
    professional["employment_status"] = classified["status"]
    master["professional"] = professional
    master["employment_extended"] = {
        **(master.get("employment_extended") if isinstance(master.get("employment_extended"), dict) else {}),
        "kind": kind,
        "note": classified["note"],
    }
    profile.master_data = master
    flag_modified(profile, "master_data")
    flag_modified(profile, "work_history")

    prefs = db.scalar(select(ApplicationPreferences).where(ApplicationPreferences.user_id == user.id))
    master_profile_service._sync_structured_to_engine(profile, user, prefs)
    db.commit()
    db.refresh(user)
    payload = master_profile_service.master_profile_payload(db, user)
    return {
        "source": source,
        "kind": kind,
        "status": classified["status"],
        "note": classified["note"],
        "jobs": list(profile.work_history or []),
        "experience_years": profile.experience_years,
        "profile": payload,
    }
