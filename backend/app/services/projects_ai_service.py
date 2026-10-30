"""Fill Master Profile projects from the resume (academic for freshers, work projects when employed)."""

from __future__ import annotations

import copy
import json
import re
import uuid

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.app.core.errors import AppError
from backend.app.models import User
from backend.app.services import master_profile_service, resume_service, resume_text_service, run_config_service
from backend.app.services.ai_service import AiTask, ai_available, complete

_MAX_PROJECTS = 8
_MAX_TITLE = 255
_MAX_DESC = 2000
_MAX_TECH = 255


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _clip(text: str, *, limit: int) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())[:limit].rstrip()


def _skill_names(skills: list | None) -> list[str]:
    out: list[str] = []
    for item in skills or []:
        label = str(item.get("name") if isinstance(item, dict) else item or "").strip()
        if label and label not in out:
            out.append(label)
    return out


def _is_fresher(*, work_history: list | None) -> bool:
    jobs = [
        j
        for j in (work_history or [])
        if isinstance(j, dict) and (str(j.get("company") or "").strip() or str(j.get("title") or "").strip())
        and str(j.get("summary") or "").strip()
    ]
    if jobs:
        return False
    named = [
        j
        for j in (work_history or [])
        if isinstance(j, dict) and str(j.get("company") or "").strip()
    ]
    return not named


def _looks_like_title(line: str) -> bool:
    text = (line or "").strip()
    if not text or len(text) > 90:
        return False
    if text.endswith((".", ";", ",")) and len(text) > 50:
        return False
    if text.lower().startswith(("developed", "built", "implemented", "worked", "responsible", "configured")):
        return False
    return True


def _techs_from_text(text: str, skills: list[str]) -> str:
    blob = (text or "").lower()
    found = [s for s in skills if s.lower() in blob]
    return ", ".join(found[:12])


def parse_project_lines(lines: list[str], *, skills: list[str] | None = None, role: str = "") -> list[dict]:
    """Turn a Projects section into {title, description, role, technologies} rows."""
    entries: list[dict] = []
    title = ""
    body: list[str] = []
    skill_list = skills or []

    def flush() -> None:
        nonlocal title, body
        name = _clip(title, limit=_MAX_TITLE)
        if not name:
            return
        desc = _clip(" ".join(body), limit=_MAX_DESC)
        entries.append(
            {
                "title": name,
                "description": desc,
                "role": role,
                "technologies": _techs_from_text(f"{name} {desc}", skill_list),
            }
        )
        title, body = "", []

    for raw in lines or []:
        line = re.sub(r"^[•·\-\*]+\s*", "", (raw or "").strip())
        numbered = re.match(r"^\d{1,2}[.)]\s+(.+)$", line)
        if numbered:
            flush()
            title = numbered.group(1).strip()
            continue
        if _looks_like_title(line) and (not title or body):
            flush()
            title = line
            continue
        if title:
            body.append(line)
        else:
            title = line[:90]
    flush()
    return [e for e in entries if e["title"]][:_MAX_PROJECTS]


def projects_from_work_history(work_history: list | None, *, skills: list[str] | None = None) -> list[dict]:
    """Map employment rows to project cards (experienced candidates)."""
    skill_list = skills or []
    out: list[dict] = []
    for job in work_history or []:
        if not isinstance(job, dict):
            continue
        job_title = str(job.get("title") or "").strip()
        company = str(job.get("company") or "").strip()
        summary = str(job.get("summary") or "").strip()
        if not (job_title or company):
            continue
        if company and job_title:
            name = f"{job_title} at {company}"
        else:
            name = job_title or company
        out.append(
            {
                "title": _clip(name, limit=_MAX_TITLE),
                "description": _clip(summary, limit=_MAX_DESC),
                "role": _clip(job_title, limit=_MAX_TITLE),
                "technologies": _techs_from_text(f"{name} {summary}", skill_list),
            }
        )
        if len(out) >= _MAX_PROJECTS:
            break
    return out


def _resume_skill_focus(skills: list[str], *, title: str, resume_text: str) -> tuple[str, list[str]]:
    """Prefer skills that actually appear on the resume over a possibly-wrong current title."""
    blob = (resume_text or "").lower()
    guessed = resume_text_service.guess_skills_from_text(resume_text, []) if blob else []
    guessed = [re.split(r"[:/]", s, maxsplit=1)[0].strip() for s in guessed if s.strip()]
    skip = {"skills", "technical", "technical skills", "core competencies", "technologies", "tools", "other"}
    guessed = [s for s in guessed if 2 <= len(s) <= 64 and s.lower() not in skip]
    on_resume: list[str] = []
    if blob:
        for s in skills:
            if re.search(rf"\b{re.escape(s.lower())}\b", blob):
                on_resume.append(s)
    ranked: list[str] = []
    for s in guessed + on_resume + list(skills):
        if s and s.lower() not in {x.lower() for x in ranked}:
            ranked.append(s)
    focus = guessed[0] if guessed else (on_resume[0] if on_resume else (ranked[0] if ranked else (title.strip() or "coursework")))
    if title.strip() and blob and re.search(rf"\b{re.escape(title.strip().lower())}\b", blob):
        focus = title.strip()
    return focus, ranked[:12]


def fresher_academic_fallback(
    *,
    skills: list[str] | None = None,
    education: list | None = None,
    title: str = "",
    summary: str = "",
    resume_text: str = "",
) -> list[dict]:
    """When a fresher resume has no Projects heading, describe coursework from stated skills."""
    skill_list = _skill_names(skills)
    if not skill_list and not title:
        return []
    focus, ranked = _resume_skill_focus(skill_list, title=title, resume_text=resume_text)
    edu = ""
    for row in education or []:
        if not isinstance(row, dict):
            continue
        degree = str(row.get("degree") or "").strip()
        field = str(row.get("field") or "").strip()
        school = str(row.get("school") or "").strip()
        year = str(row.get("end_year") or "").strip()
        parts = " ".join(p for p in (degree, field) if p).strip()
        if school and parts:
            edu = f"{parts} at {school}"
        else:
            edu = parts or school
        if edu and year:
            edu = f"{edu} ({year})"
        if edu:
            break
    name = f"{focus} academic project"
    bits = []
    if edu:
        bits.append(f"Academic work during {edu}.")
    if summary and (not resume_text or summary.strip().lower() in resume_text.lower()):
        bits.append(_clip(summary, limit=500))
    elif ranked:
        bits.append("Hands-on practice with " + ", ".join(ranked[:10]) + ".")
    techs = ranked[:12] or skill_list[:12]
    return [
        {
            "title": _clip(name, limit=_MAX_TITLE),
            "description": _clip(" ".join(bits), limit=_MAX_DESC),
            "role": "Student",
            "technologies": ", ".join(techs),
        }
    ]


def heuristic_projects(
    *,
    resume_text: str = "",
    work_history: list | None = None,
    skills: list | None = None,
    education: list | None = None,
    title: str = "",
    summary: str = "",
) -> tuple[list[dict], str]:
    """
    Return (projects, kind) where kind is academic | professional.
    Freshers: resume Projects section, else academic fallback from skills/education.
    Experienced: resume Projects section plus employment project experience.
    """
    skill_list = _skill_names(skills)
    fresher = _is_fresher(work_history=work_history)
    parsed = parse_project_lines(resume_text_service.project_section_lines(resume_text), skills=skill_list)
    if fresher:
        if parsed:
            return parsed, "academic"
        fallback = fresher_academic_fallback(
            skills=skill_list,
            education=education,
            title=title,
            summary=summary,
            resume_text=resume_text,
        )
        return fallback, "academic"
    from_jobs = projects_from_work_history(work_history, skills=skill_list)
    merged = _uniq_projects(parsed + from_jobs)
    return merged, "professional"


def _uniq_projects(rows: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for row in rows:
        title = _clip(str(row.get("title") or ""), limit=_MAX_TITLE)
        key = _compact(title)
        if not title or key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "id": str(row.get("id") or uuid.uuid4()),
                "title": title,
                "description": _clip(str(row.get("description") or ""), limit=_MAX_DESC),
                "role": _clip(str(row.get("role") or ""), limit=_MAX_TITLE),
                "technologies": _clip(str(row.get("technologies") or ""), limit=_MAX_TECH),
            }
        )
        if len(out) >= _MAX_PROJECTS:
            break
    return out


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
        raise AppError("AI_PARSE_ERROR", "Could not parse AI project suggestions.", 502) from exc
    return data if isinstance(data, dict) else {}


def _llm_projects(db: Session, *, resume_text: str, fresher: bool, skills: list[str]) -> list[dict]:
    kind = "academic or coursework/lab projects" if fresher else "professional project experience from jobs"
    system = (
        f"Extract {kind} from this resume. Output ONLY JSON with key projects "
        "(array of {title, description, role, technologies}). "
        "Use only resume facts. Do not invent employers, products, or dates. "
        "If the resume has no projects, return {\"projects\": []}. "
        f"Candidate skills: {', '.join(skills[:20])}."
    )
    raw = complete(
        db,
        AiTask.APP_ANSWER,
        system=system,
        user=(resume_text or "")[:9000],
        feature="applications",
        temperature=0.2,
        max_tokens=1400,
    )
    data = _parse_json(raw)
    rows = data.get("projects") if isinstance(data.get("projects"), list) else []
    out: list[dict] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        title = _clip(str(item.get("title") or ""), limit=_MAX_TITLE)
        if not title:
            continue
        out.append(
            {
                "title": title,
                "description": _clip(str(item.get("description") or ""), limit=_MAX_DESC),
                "role": _clip(str(item.get("role") or ""), limit=_MAX_TITLE),
                "technologies": _clip(str(item.get("technologies") or ""), limit=_MAX_TECH),
            }
        )
    return out


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


def fill_projects_from_resume(db: Session, user: User) -> dict:
    if user.profile is None:
        raise AppError("VALIDATION_ERROR", "Create a profile first.", 422)
    profile = user.profile
    master = copy.deepcopy(master_profile_service.ensure_master_data(profile))
    skills = list(profile.skills or [])
    if not skills:
        skills = [s.get("name") for s in (master.get("skills") or []) if isinstance(s, dict) and s.get("name")]
    work = list(profile.work_history or [])
    resume_text = _resume_text(db, user.id)
    suggested, kind = heuristic_projects(
        resume_text=resume_text,
        work_history=work,
        skills=skills,
        education=list(profile.education or []),
        title=profile.current_title or "",
        summary=profile.summary or "",
    )
    source = "heuristic"
    if resume_text and (ai_available(db, feature="applications") or ai_available(db, feature="resume")):
        try:
            ai_rows = _llm_projects(
                db,
                resume_text=resume_text,
                fresher=_is_fresher(work_history=work),
                skills=_skill_names(skills),
            )
            if ai_rows:
                suggested = _uniq_projects(ai_rows + suggested)
                source = "ai"
        except AppError:
            pass

    existing = [p for p in (master.get("projects") or []) if isinstance(p, dict) and str(p.get("title") or "").strip()]
    if kind == "academic" and suggested:
        existing = [
            p
            for p in existing
            if "academic project" not in str(p.get("title") or "").lower()
        ]
    merged = _uniq_projects(existing + suggested)
    added = [p["title"] for p in merged if _compact(p["title"]) not in {_compact(str(e.get("title") or "")) for e in existing}]
    master["projects"] = merged
    profile.master_data = master
    flag_modified(profile, "master_data")
    db.commit()
    db.refresh(user)
    payload = master_profile_service.master_profile_payload(db, user)
    return {
        "source": source,
        "kind": kind,
        "added": added,
        "projects": merged,
        "profile": payload,
    }
