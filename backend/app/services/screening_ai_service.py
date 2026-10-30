"""Fill Master Profile engine screening answers from resume and profile facts."""

from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.app.core.errors import AppError
from backend.app.models import User
from backend.app.schemas.application_preferences import MAX_USER_INFO
from backend.app.services import application_context, master_profile_service, preferences_service, run_config_service
from backend.app.services.ai_service import AiTask, ai_available, complete
from backend.app.services.engine_fields import MAX_TEXTAREA, PROFILE_ANSWER_FIELDS, validate_mapping
from backend.app.services.resume_text_service import format_user_information_block

_NARRATIVE_KEYS = ("user_information_all", "cover_letter")
_LEGAL_KEYS = {
    "require_visa",
    "legally_authorized",
    "us_citizenship",
    "ethnicity",
    "gender",
    "disability_status",
    "veteran_status",
}


def _present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _clip(text: str, *, limit: int) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())[:limit].rstrip()


def _education_line(education: list | None) -> str:
    for row in education or []:
        if not isinstance(row, dict):
            continue
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
        if line:
            return line
    return ""


def heuristic_screening_answers(
    *,
    name: str = "",
    title: str = "",
    headline: str = "",
    summary: str = "",
    city: str = "",
    skills: list | None = None,
    education: list | None = None,
    work_history: list | None = None,
    roles: list | None = None,
    experience_years: float | int | None = None,
    current_company: str = "",
    professional: dict | None = None,
    personal: dict | None = None,
    career: dict | None = None,
    engine: dict | None = None,
) -> dict:
    """Draft screening values from structured facts. Does not invent employers or legal status."""
    prof = professional or {}
    personal = personal or {}
    career = career or {}
    engine = engine or {}
    skill_names = []
    for item in skills or []:
        label = str(item.get("name") if isinstance(item, dict) else item or "").strip()
        if label and label not in skill_names:
            skill_names.append(label)
    edu = _education_line(education)
    role_list = [str(r).strip() for r in (roles or []) if str(r).strip()]
    out: dict = {}

    intake = {
        "skills": skill_names,
        "work_history": [j for j in (work_history or []) if isinstance(j, dict)],
        "education": [e for e in (education or []) if isinstance(e, dict)],
        "current_title": title,
        "current_company": current_company,
    }
    facts = format_user_information_block(intake)
    extra: list[str] = []
    if name:
        extra.append(f"Name: {name}")
    if city:
        extra.append(f"Location: {city}")
    if experience_years is not None:
        extra.append(f"Years of experience: {experience_years}")
    if headline:
        extra.append(f"Headline: {headline}")
    if summary and summary.strip() != headline.strip():
        extra.append(f"Summary: {summary.strip()}")
    if role_list:
        extra.append("Preferred roles: " + ", ".join(role_list[:8]))
    block = "\n".join([*extra, facts]).strip()
    if block:
        out["user_information_all"] = block[:MAX_USER_INFO]

    who = name.strip() or "I"
    focus = role_list[0] if role_list else (title.strip() or "this role")
    skill_text = ", ".join(skill_names[:8])
    letter_bits = [
        "Dear Hiring Manager,",
        "",
        f"I am {who}" + (f", a {title}" if title else "") + (f" based in {city}" if city else "") + ".",
    ]
    if edu:
        letter_bits.append(f"I completed {edu}.")
    if skill_text:
        letter_bits.append(f"I work with {skill_text} and am looking for {focus} opportunities where I can contribute from day one.")
    else:
        letter_bits.append(f"I am looking for {focus} opportunities where I can contribute from day one.")
    letter_bits.extend(["", "Thank you for your consideration.", who])
    out["cover_letter"] = _clip(" ".join(letter_bits), limit=MAX_TEXTAREA)

    if experience_years is not None:
        out["years_of_experience"] = str(int(experience_years))
    if city:
        out["current_city"] = city
    for src, dest in (
        ("street", "street"),
        ("state", "state"),
        ("postal_code", "zipcode"),
        ("country", "country"),
        ("middle_name", "middle_name"),
        ("gender", "gender"),
        ("ethnicity", "ethnicity"),
    ):
        val = str(personal.get(src) or "").strip()
        if val:
            out[dest] = val
    if prof.get("expected_ctc") is not None:
        out["desired_salary"] = int(prof["expected_ctc"])
    elif engine.get("desired_salary") not in (None, ""):
        try:
            out["desired_salary"] = int(engine["desired_salary"])
        except (TypeError, ValueError):
            pass
    if prof.get("current_ctc") is not None:
        out["current_ctc"] = int(prof["current_ctc"])
    if prof.get("notice_period_days") is not None:
        out["notice_period"] = int(prof["notice_period_days"])
    if career.get("linkedin_url"):
        out["linkedIn"] = str(career["linkedin_url"]).strip()
    elif engine.get("linkedIn"):
        out["linkedIn"] = str(engine["linkedIn"]).strip()
    if career.get("portfolio_url"):
        out["website"] = str(career["portfolio_url"]).strip()
    if current_company:
        out["recent_employer"] = current_company
    if prof.get("confidence_level"):
        out["confidence_level"] = str(prof["confidence_level"]).strip()
    for key in ("disability_status", "veteran_status"):
        # diversity is passed via personal overlay in fill_screening
        val = str(personal.get(key) or "").strip()
        if val:
            out[key] = val
    for key in ("legally_authorized", "require_visa"):
        val = str(engine.get(key) or "").strip()
        if val:
            out[key] = val.capitalize() if val.lower() in ("yes", "no") else val
    return {k: v for k, v in out.items() if _present(v)}


def _merge_fact_lines(ai_text: str, heuristic_text: str) -> str:
    """Keep the AI draft, then append heuristic fact lines the model omitted (skills, education)."""
    base = (ai_text or "").strip()
    have = base.lower()
    extras: list[str] = []
    for line in (heuristic_text or "").splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        label = line.split(":", 1)[0].strip().lower()
        if label and label not in have:
            extras.append(line)
    if extras:
        base = (base + "\n" + "\n".join(extras)).strip()
    return base[:MAX_USER_INFO]


def _thin_facts(value: object) -> bool:
    text = str(value or "").lower()
    return bool(text.strip()) and "skill" not in text


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
        raise AppError("AI_PARSE_ERROR", "Could not parse AI screening answers.", 502) from exc
    return data if isinstance(data, dict) else {}


def _llm_narratives(db: Session, *, context: str, keys: list[str]) -> dict[str, str]:
    system = (
        "Draft job-application screening text from the candidate context and resume. Output ONLY JSON. "
        "Keys may include user_information_all (plain-text facts: name, location, education, skills, "
        "roles; one fact per line; no invented employers) and cover_letter (120-220 words, first person, "
        "professional, sign with the candidate name). Use only stated facts. Omit a key if you cannot "
        "write it honestly."
    )
    raw = complete(
        db,
        AiTask.APP_ANSWER,
        system=system,
        user=json.dumps({"candidate_context": context[:9000], "keys": keys}, ensure_ascii=False)[:12000],
        feature="applications",
        temperature=0.3,
        max_tokens=1400,
    )
    data = _parse_json(raw)
    out: dict[str, str] = {}
    for key in keys:
        text = str(data.get(key) or "").strip()
        if text:
            out[key] = text[: MAX_USER_INFO if key == "user_information_all" else MAX_TEXTAREA]
    return out


def fill_screening_from_resume(db: Session, user: User) -> dict:
    if user.profile is None:
        raise AppError("VALIDATION_ERROR", "Create a profile first.", 422)
    profile = user.profile
    master = master_profile_service.ensure_master_data(profile)
    personal = dict(master.get("personal") or {})
    diversity = dict(master.get("diversity") or {})
    personal.update({k: v for k, v in diversity.items() if v})
    professional = dict(master.get("professional") or {})
    career = dict(master.get("career") or {})
    engine = run_config_service.engine_values(db, user.id)
    skills = list(profile.skills or [])
    if not skills:
        skills = [s.get("name") for s in (master.get("skills") or []) if isinstance(s, dict) and s.get("name")]
    suggested = heuristic_screening_answers(
        name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
        title=profile.current_title or "",
        headline=profile.headline or "",
        summary=profile.summary or "",
        city=str(personal.get("city") or ""),
        skills=skills,
        education=list(profile.education or []),
        work_history=list(profile.work_history or []),
        roles=list(profile.preferred_roles or []) or list(career.get("preferred_roles") or []),
        experience_years=profile.experience_years,
        current_company=profile.current_company or "",
        professional=professional,
        personal=personal,
        career=career,
        engine=engine,
    )
    source = "heuristic"
    prefs = preferences_service._application_row(db, user)
    answers = dict(prefs.answers or {})
    if not _present(answers.get("user_information_all")) and (prefs.user_information_all or "").strip():
        suggested["user_information_all"] = prefs.user_information_all.strip()[:MAX_USER_INFO]

    empty_narratives = [
        k
        for k in _NARRATIVE_KEYS
        if not _present(answers.get(k)) or (k == "user_information_all" and _thin_facts(answers.get(k)))
    ]
    if empty_narratives and (ai_available(db, feature="applications") or ai_available(db, feature="profile_sync")):
        try:
            ctx = application_context.build_context(db, user.id, include_default_resume=True)
            ai = _llm_narratives(db, context=ctx, keys=empty_narratives)
            heur_info = str(suggested.get("user_information_all") or "")
            if ai.get("user_information_all"):
                suggested["user_information_all"] = _merge_fact_lines(ai["user_information_all"], heur_info)
            if ai.get("cover_letter"):
                suggested["cover_letter"] = ai["cover_letter"]
            source = "ai"
        except AppError:
            pass

    filled: list[str] = []
    patch: dict = {}
    for key, field in PROFILE_ANSWER_FIELDS.items():
        existing = answers.get(key)
        if _present(existing) and not (key == "user_information_all" and _thin_facts(existing)):
            continue
        if key in _LEGAL_KEYS and key not in suggested:
            continue
        value = suggested.get(key)
        if not _present(value):
            continue
        if field["type"] in ("text", "textarea") and isinstance(value, str):
            limit = MAX_TEXTAREA if field["type"] == "textarea" else 1000
            value = value[:limit]
        patch[key] = value
        filled.append(key)

    if patch:
        cleaned = validate_mapping(PROFILE_ANSWER_FIELDS, patch, allow_null=False)
        answers.update(cleaned)
        prefs.answers = answers
        flag_modified(prefs, "answers")
        uinfo = cleaned.get("user_information_all")
        if isinstance(uinfo, str) and uinfo.strip() and not (prefs.user_information_all or "").strip():
            prefs.user_information_all = uinfo.strip()[:MAX_USER_INFO]
        db.commit()

    return {
        "source": source,
        "filled": filled,
        "answers": {k: answers.get(k) for k in filled},
    }
