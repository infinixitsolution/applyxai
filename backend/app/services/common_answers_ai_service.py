"""Fill Master Profile common application answers from resume and profile facts."""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.app.core.errors import AppError
from backend.app.core.profile_taxonomies import COMMON_ANSWER_TEMPLATES
from backend.app.models import ApplicationPreferences, User
from backend.app.services import application_context, master_profile_service, run_config_service
from backend.app.services.ai_service import AiTask, ai_available, complete

_NARRATIVE_KEYS = {
    "about_yourself",
    "why_role",
    "why_hire",
    "strengths",
    "weaknesses",
    "achievement",
    "career_goals",
    "leaving_job",
    "relocate",
}
_PROFILE_FIELD_KEYS = {"expected_salary", "current_salary", "notice_period", "when_join"}
_LEGAL_KEYS = {"work_auth", "visa_sponsor"}
_MAX_ANSWER = 1500


def _compact_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _clip(text: str, *, limit: int = _MAX_ANSWER) -> str:
    value = _compact_space(text)
    return value[:limit].rstrip() if value else ""


def _names(skills: list | None, *, limit: int = 8) -> list[str]:
    out: list[str] = []
    for item in skills or []:
        if isinstance(item, dict):
            label = str(item.get("name") or "").strip()
        else:
            label = str(item or "").strip()
        if label and label not in out:
            out.append(label)
        if len(out) >= limit:
            break
    return out


def _phrase(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _first_dict(rows: list | None) -> dict:
    for row in rows or []:
        if isinstance(row, dict):
            return row
    return {}


def _education_line(education: list | None) -> str:
    row = _first_dict(education)
    if not row:
        return ""
    degree = str(row.get("degree") or "").strip()
    field = str(row.get("field") or "").strip()
    school = str(row.get("school") or "").strip()
    year = str(row.get("end_year") or row.get("year") or "").strip()
    parts = " ".join(p for p in (degree, field) if p).strip()
    if school and parts:
        line = f"{parts} from {school}"
    else:
        line = parts or school
    if line and year:
        line = f"{line} ({year})"
    return line


def _is_fresher(*, years: float | int | None, work_history: list | None) -> bool:
    jobs = [j for j in (work_history or []) if isinstance(j, dict) and (j.get("company") or j.get("title"))]
    if jobs:
        return False
    if years is None:
        return True
    try:
        return float(years) <= 1
    except (TypeError, ValueError):
        return True


def _yes_no(value: object) -> str:
    raw = str(value or "").strip()
    low = raw.lower()
    if low in ("yes", "true", "1", "y"):
        return "Yes"
    if low in ("no", "false", "0", "n"):
        return "No"
    return raw


def heuristic_common_answers(
    *,
    name: str = "",
    title: str = "",
    headline: str = "",
    summary: str = "",
    city: str = "",
    skills: list | None = None,
    education: list | None = None,
    work_history: list | None = None,
    projects: list | None = None,
    roles: list | None = None,
    locations: list | None = None,
    experience_years: float | int | None = None,
    professional: dict | None = None,
    engine: dict | None = None,
) -> dict[str, str]:
    """Draft reusable answers from structured profile facts. Does not invent employers or legal status."""
    prof = professional or {}
    engine = engine or {}
    skill_list = _names(skills)
    skill_text = _phrase(skill_list)
    edu = _education_line(education)
    role_list = [str(r).strip() for r in (roles or []) if str(r).strip()]
    loc_list = [str(loc).strip() for loc in (locations or []) if str(loc).strip()]
    role_text = _phrase(role_list[:4]) or title.strip() or "this"
    focus = role_list[0] if role_list else (title.strip() or "this field")
    who = name.strip() or "I"
    where = city.strip() or (loc_list[0] if loc_list else "")
    fresher = _is_fresher(years=experience_years, work_history=work_history)
    job = _first_dict(work_history)
    project = _first_dict(projects)

    out: dict[str, str] = {}
    summary_text = _clip(summary, limit=800)
    if summary_text and len(summary_text) >= 40:
        out["about_yourself"] = summary_text
    else:
        bits = []
        if who != "I":
            opener = f"I am {who}"
            if title:
                opener += f", a {title}"
            if where:
                opener += f" based in {where}"
            bits.append(opener + ".")
        elif title:
            bits.append(f"I am a {title}" + (f" based in {where}." if where else "."))
        if headline and headline.lower() not in " ".join(bits).lower():
            bits.append(headline.rstrip(".") + ".")
        if edu:
            bits.append(f"I completed {edu}.")
        if skill_text:
            bits.append(f"My skills include {skill_text}.")
        if role_text and role_text != "this":
            bits.append(f"I am looking for {role_text} opportunities.")
        out["about_yourself"] = _clip(" ".join(bits))

    if skill_text or role_text:
        out["why_role"] = _clip(
            f"I am interested in {role_text} roles where I can apply "
            f"{skill_text or 'my training'} and keep growing in {focus}."
        )
        out["why_hire"] = _clip(
            (
                f"I bring {skill_text}"
                + (f" along with {edu}" if edu else "")
                + ". I learn quickly, communicate clearly, and am ready to contribute from day one."
            )
            if skill_text or edu
            else f"I am motivated to succeed in {focus} and ready to contribute from day one."
        )
        out["strengths"] = _clip(
            f"My strengths include {skill_text}. I follow through on tasks and stay organized under deadlines."
            if skill_text
            else "I communicate clearly, stay organized, and follow through on commitments."
        )

    if fresher:
        out["weaknesses"] = (
            "I am still building production-scale experience and close that gap through labs, "
            "certifications, and focused practice."
        )
        out["leaving_job"] = (
            "I am seeking my first full-time role where I can apply my training and grow with a team."
        )
    else:
        out["weaknesses"] = (
            "I can take on too many details myself. I am getting better at documenting and sharing work "
            "so the team can move faster."
        )
        company = str(job.get("company") or "").strip()
        out["leaving_job"] = _clip(
            f"I am looking for a better match with my skills in {focus}"
            + (f" than my current role at {company}" if company else "")
            + "."
        )

    proj_title = str(project.get("title") or "").strip()
    proj_desc = str(project.get("description") or "").strip()
    job_summary = str(job.get("summary") or "").strip()
    if proj_title:
        out["achievement"] = _clip(
            f"{proj_title}" + (f" — {proj_desc}" if proj_desc else ".")
        )
    elif job_summary:
        out["achievement"] = _clip(job_summary)
    elif edu:
        out["achievement"] = _clip(f"Completing {edu} while building practical skills in {skill_text or focus}.")

    out["career_goals"] = _clip(
        f"I want to grow as a {focus} and take on more ownership of {skill_text or 'the work'} over the next few years."
    )

    remote = any("remote" in loc.lower() for loc in loc_list)
    if remote:
        out["relocate"] = "Yes — open to remote work and willing to relocate for the right role."
    elif where or loc_list:
        place = where or loc_list[0]
        out["relocate"] = f"I am based in {place} and open to relocation for the right opportunity."

    if prof.get("expected_ctc") is not None:
        out["expected_salary"] = str(prof["expected_ctc"])
    elif engine.get("desired_salary"):
        out["expected_salary"] = str(engine["desired_salary"])
    if prof.get("current_ctc") is not None:
        out["current_salary"] = str(prof["current_ctc"])
    elif engine.get("current_ctc"):
        out["current_salary"] = str(engine["current_ctc"])
    notice = prof.get("notice_period_days")
    if notice is not None:
        out["notice_period"] = f"{notice} days" if str(notice) != "0" else "Immediate"
    elif engine.get("notice_period") not in (None, ""):
        days = engine.get("notice_period")
        out["notice_period"] = f"{days} days" if str(days) != "0" else "Immediate"
    avail = str(prof.get("availability_description") or prof.get("availability_type") or "").strip()
    if avail:
        out["when_join"] = avail

    auth = _yes_no(engine.get("legally_authorized"))
    if auth:
        out["work_auth"] = auth
    visa = _yes_no(engine.get("require_visa"))
    if visa:
        out["visa_sponsor"] = visa

    return {k: v for k, v in out.items() if _clip(v)}


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
        raise AppError("AI_PARSE_ERROR", "Could not parse AI application answers.", 502) from exc
    return data if isinstance(data, dict) else {}


def _llm_answers(db: Session, *, context: str, questions: list[dict]) -> dict[str, str]:
    keys = [q["key"] for q in questions]
    system = (
        "Fill job-application narrative answers for this candidate. Output ONLY JSON whose keys are "
        "exactly the requested answer keys. Use only facts from the context and resume. "
        "Do not invent employers, degrees, dates, salary, visa status, or work authorization. "
        "If a fact is missing, omit that key. Narrative answers: 60-120 words, first person, professional. "
        "Salary and notice: short (number or 'X days'). Yes/no questions: Yes or No only when the context states it."
    )
    payload = {
        "candidate_context": context[:9000],
        "questions": questions,
        "required_keys": keys,
    }
    raw = complete(
        db,
        AiTask.APP_ANSWER,
        system=system,
        user=json.dumps(payload, ensure_ascii=False)[:12000],
        feature="applications",
        temperature=0.3,
        max_tokens=1800,
    )
    data = _parse_json(raw)
    out: dict[str, str] = {}
    allowed = {q["key"] for q in questions}
    for key, value in data.items():
        if key not in allowed:
            continue
        text = _clip(str(value or ""))
        if text:
            out[key] = text
    return out


def fill_common_answers_from_resume(db: Session, user: User) -> dict:
    if user.profile is None:
        raise AppError("VALIDATION_ERROR", "Create a profile first.", 422)
    profile = user.profile
    master = copy.deepcopy(master_profile_service.ensure_master_data(profile))
    master_profile_service._seed_common_answers(master)
    personal = master.get("personal") or {}
    professional = dict(master.get("professional") or {})
    career = master.get("career") or {}
    engine = run_config_service.engine_values(db, user.id)
    skills = list(profile.skills or [])
    if not skills:
        skills = [s.get("name") for s in (master.get("skills") or []) if isinstance(s, dict) and s.get("name")]
    roles = list(profile.preferred_roles or []) or list(career.get("preferred_roles") or [])
    locations = list(profile.preferred_locations or []) or list(career.get("preferred_locations") or [])
    suggested = heuristic_common_answers(
        name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
        title=profile.current_title or "",
        headline=profile.headline or "",
        summary=profile.summary or "",
        city=str(personal.get("city") or ""),
        skills=skills,
        education=list(profile.education or []),
        work_history=list(profile.work_history or []),
        projects=list(master.get("projects") or []),
        roles=roles,
        locations=locations,
        experience_years=profile.experience_years,
        professional=professional,
        engine=engine,
    )
    source = "heuristic"

    existing = [a for a in (master.get("common_answers") or []) if isinstance(a, dict)]
    empty_keys = [
        str(a.get("key") or "")
        for a in existing
        if str(a.get("key") or "") and not str(a.get("answer") or "").strip() and not a.get("verified")
    ]
    pending = [tpl for tpl in COMMON_ANSWER_TEMPLATES if tpl["key"] in empty_keys]
    if pending and (ai_available(db, feature="applications") or ai_available(db, feature="profile_sync")):
        try:
            ctx = application_context.build_context(db, user.id, include_default_resume=True)
            ai = _llm_answers(
                db,
                context=ctx,
                questions=[{"key": t["key"], "question": t["question"]} for t in pending],
            )
            for key, value in ai.items():
                if key in _PROFILE_FIELD_KEYS:
                    continue
                if key in _LEGAL_KEYS and key not in suggested:
                    continue
                suggested[key] = value
            source = "ai"
        except AppError:
            pass

    filled: list[str] = []
    skipped_verified: list[str] = []
    now = datetime.now(timezone.utc).isoformat()
    for item in existing:
        key = str(item.get("key") or "")
        if item.get("verified"):
            if str(item.get("answer") or "").strip():
                skipped_verified.append(key)
            continue
        if str(item.get("answer") or "").strip():
            continue
        value = suggested.get(key)
        if not value:
            continue
        item["answer"] = value
        item["updated_at"] = now
        filled.append(key)

    master["common_answers"] = existing
    profile.master_data = master
    flag_modified(profile, "master_data")
    prefs = db.scalar(select(ApplicationPreferences).where(ApplicationPreferences.user_id == user.id))
    master_profile_service._sync_structured_to_engine(profile, user, prefs)
    db.commit()
    db.refresh(user)
    payload = master_profile_service.master_profile_payload(db, user)
    return {
        "source": source,
        "filled": filled,
        "skipped_verified": skipped_verified,
        "profile": payload,
    }
