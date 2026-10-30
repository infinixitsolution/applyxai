"""Complete Professional overview headline and summary from the resume."""

from __future__ import annotations

import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.models import ApplicationPreferences, User
from backend.app.services import master_profile_service, resume_service, resume_text_service, run_config_service
from backend.app.services.ai_service import AiTask, ai_available, complete

_MAX_HEADLINE = 255
_MAX_SUMMARY = 5000


def _clip(text: str, *, limit: int) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())[:limit].rstrip()


def _skill_names(skills: list | None) -> list[str]:
    out: list[str] = []
    for item in skills or []:
        label = str(item.get("name") if isinstance(item, dict) else item or "").strip()
        if label and label not in out:
            out.append(label)
    return out


def _is_stub(text: str, *, min_len: int = 40) -> bool:
    value = (text or "").strip()
    if not value:
        return True
    if len(value) < min_len:
        return True
    return value.lower() in {"na", "n/a", "none", "tbd"}


def _education_line(education: list | None) -> str:
    for row in education or []:
        if not isinstance(row, dict):
            continue
        degree = str(row.get("degree") or "").strip()
        field = str(row.get("field") or "").strip()
        school = str(row.get("school") or "").strip()
        year = str(row.get("end_year") or "").strip()
        parts = " ".join(p for p in (degree, field) if p).strip()
        if school and parts:
            line = f"{parts} from {school}"
        else:
            line = parts or school
        if line and year:
            line = f"{line} ({year})"
        if line:
            return line
    return ""


def _resume_skills(resume_text: str, skills: list[str]) -> list[str]:
    blob = (resume_text or "").lower()
    guessed = resume_text_service.guess_skills_from_text(resume_text, []) if blob else []
    skip = {"skills", "technical", "technical skills", "core competencies", "technologies", "tools", "other"}
    cleaned: list[str] = []
    for raw in guessed:
        token = re.split(r"[:/]", raw, maxsplit=1)[0].strip()
        if 2 <= len(token) <= 40 and token.lower() not in skip and token not in cleaned:
            cleaned.append(token)
    on_resume: list[str] = []
    if blob:
        for s in skills:
            if re.search(rf"\b{re.escape(s.lower())}\b", blob) and s not in on_resume:
                on_resume.append(s)
    ranked: list[str] = []
    for s in cleaned + on_resume + skills:
        if s and s.lower() not in {x.lower() for x in ranked}:
            ranked.append(s)
    return ranked[:12]


def heuristic_professional_overview(
    *,
    resume_text: str = "",
    title: str = "",
    city: str = "",
    skills: list | None = None,
    education: list | None = None,
    work_history: list | None = None,
    experience_years: float | int | None = None,
) -> dict[str, str]:
    skill_list = _resume_skills(resume_text, _skill_names(skills))
    jobs = [
        j
        for j in (work_history or [])
        if isinstance(j, dict) and str(j.get("company") or "").strip()
    ]
    fresher = not jobs
    objective = resume_text_service.extract_summary_block(resume_text) or ""
    edu = _education_line(education)
    focus = skill_list[0] if skill_list else (title.strip() or "IT")
    if title.strip() and resume_text and title.strip().lower() in resume_text.lower():
        focus = title.strip()
    headline_bits = [focus]
    if skill_list:
        extra = [s for s in skill_list[1:4] if s.lower() not in focus.lower()]
        if extra:
            headline_bits.append(" · ".join(extra[:3]))
    if city:
        headline_bits.append(city)
    headline = " · ".join(headline_bits)[:_MAX_HEADLINE]
    if objective and len(objective) >= 40:
        summary = _clip(objective, limit=_MAX_SUMMARY)
    else:
        bits = [f"I am a {focus}" + (" looking for a first full-time role" if fresher else "") + "."]
        if edu:
            bits.append(f"I completed {edu}.")
        if skill_list:
            bits.append("Skills include " + ", ".join(skill_list[:8]) + ".")
        if jobs:
            job = jobs[0]
            bits.append(
                f"Most recently {job.get('title') or 'worked'} at {job.get('company')}."
            )
        elif experience_years is not None:
            bits.append(f"Total experience: {int(experience_years)} years.")
        summary = _clip(" ".join(bits), limit=_MAX_SUMMARY)
    return {"headline": _clip(headline, limit=_MAX_HEADLINE), "summary": summary}


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
        raise AppError("AI_PARSE_ERROR", "Could not parse AI professional overview.", 502) from exc
    return data if isinstance(data, dict) else {}


def _llm_overview(db: Session, *, resume_text: str, facts: dict) -> dict[str, str]:
    system = (
        "Write a LinkedIn-style professional overview from the resume. Output ONLY JSON with keys "
        "headline (max 120 characters, role + skills + city) and summary (80-140 words, first person). "
        "Use only resume facts. Do not invent employers, degrees, or years of experience. "
        "If they are a fresher with no jobs, say so plainly and do not claim work experience."
    )
    raw = complete(
        db,
        AiTask.APP_ANSWER,
        system=system,
        user=json.dumps({"resume": (resume_text or "")[:8000], "facts": facts}, ensure_ascii=False)[:12000],
        feature="applications",
        temperature=0.3,
        max_tokens=700,
    )
    data = _parse_json(raw)
    headline = _clip(str(data.get("headline") or ""), limit=_MAX_HEADLINE)
    summary = str(data.get("summary") or "").strip()[:_MAX_SUMMARY]
    summary = re.sub(r"\n{3,}", "\n\n", summary)
    return {"headline": headline, "summary": summary}


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


def complete_professional_overview(db: Session, user: User) -> dict:
    if user.profile is None:
        raise AppError("VALIDATION_ERROR", "Create a profile first.", 422)
    profile = user.profile
    master = master_profile_service.ensure_master_data(profile)
    personal = master.get("personal") or {}
    skills = list(profile.skills or [])
    if not skills:
        skills = [s.get("name") for s in (master.get("skills") or []) if isinstance(s, dict) and s.get("name")]
    resume_text = _resume_text(db, user.id)
    suggested = heuristic_professional_overview(
        resume_text=resume_text,
        title=profile.current_title or "",
        city=str(personal.get("city") or ""),
        skills=skills,
        education=list(profile.education or []),
        work_history=list(profile.work_history or []),
        experience_years=profile.experience_years,
    )
    source = "heuristic"
    if resume_text and (ai_available(db, feature="applications") or ai_available(db, feature="profile_sync")):
        try:
            ai = _llm_overview(
                db,
                resume_text=resume_text,
                facts={
                    "name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                    "title": profile.current_title,
                    "city": personal.get("city"),
                    "education": (profile.education or [])[:3],
                    "skills": _skill_names(skills)[:20],
                    "experience_years": profile.experience_years,
                    "has_jobs": bool(profile.work_history),
                },
            )
            if ai.get("headline"):
                suggested["headline"] = ai["headline"]
            if ai.get("summary") and len(ai["summary"]) >= 40:
                suggested["summary"] = ai["summary"]
            source = "ai"
        except AppError:
            pass

    filled: list[str] = []
    if suggested.get("headline") and _is_stub(profile.headline or "", min_len=24):
        profile.headline = suggested["headline"]
        filled.append("headline")
    if suggested.get("summary"):
        profile.summary = suggested["summary"]
        filled.append("summary")

    prefs = db.scalar(select(ApplicationPreferences).where(ApplicationPreferences.user_id == user.id))
    master_profile_service._sync_structured_to_engine(profile, user, prefs)
    db.commit()
    db.refresh(user)
    payload = master_profile_service.master_profile_payload(db, user)
    return {
        "source": source,
        "headline": profile.headline or "",
        "summary": profile.summary or "",
        "filled": filled,
        "profile": payload,
    }
