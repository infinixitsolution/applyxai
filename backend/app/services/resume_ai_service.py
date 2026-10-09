"""JD-gated resume tailoring with locked master skills."""

from __future__ import annotations

import io
import json
import re
import uuid
from pathlib import Path

from fastapi import UploadFile

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.models import ApplicationPreferences, Resume, SearchConfig, User, UserProfile
from backend.app.services import application_service, preferences_service, resume_service, resume_text_service
from backend.app.services.ai_service import AiTask, ai_available, complete
from backend.app.services.engine_fields import APPLICATION_FIELDS, validate_value
from backend.app.services.resume_templates import get_template, preferred_template_for_user

_GATE_MIN = 60
_FIT_TARGET = 90
_MAX_REFINE = 2


def _keywords(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zA-Z+#][a-zA-Z0-9+#.\-]{1,48}", (text or "").lower()) if len(w) > 2}


def match_score(master_skills: list[str], resume_text: str, job_description: str) -> tuple[int, list[str]]:
    jd_kw = _keywords(job_description)
    if not jd_kw:
        return 0, []
    have = {s.lower() for s in master_skills} | _keywords(resume_text)
    overlap = jd_kw & have
    score = int(round(100 * len(overlap) / max(len(jd_kw), 1)))
    missing = sorted(jd_kw - have)[:40]
    return min(score, 100), missing


def _ats_score(master_skills: list[str], resume_text: str, jd: str, patch: dict) -> int:
    base = match_score(master_skills, resume_text + " " + " ".join(patch.get("jd_tools_display") or []), jd)[0]
    return min(100, base + len(patch.get("skills_order") or []) // 10)


def validate_tailor_patch(master_skills: list[str], jd: str, resume_text: str, patch: dict) -> list[str]:
    problems: list[str] = []
    masters = {s.lower() for s in master_skills}
    for skill in patch.get("subskills_display") or []:
        parent = str(skill.get("master") or "").lower()
        if parent and parent not in masters:
            problems.append(f"Subskill references unknown master: {skill.get('master')}")
    jd_kw = _keywords(jd)
    for tool in patch.get("jd_tools_display") or []:
        name = str(tool.get("name") or "")
        if name.lower() not in jd_kw:
            problems.append(f"JD tool not in job description: {name}")
        evidence = str(tool.get("evidence") or "")
        if evidence and evidence.lower() not in resume_text.lower():
            problems.append(f"No evidence in resume for tool: {name}")
    lower_resume = resume_text.lower()
    for edit in patch.get("bullet_edits") or []:
        find = str(edit.get("find") or "")
        repl = str(edit.get("replace") or "")
        if len(find) < 12:
            problems.append("Bullet edit snippet too short; use a longer exact quote from the resume.")
        elif find.lower() not in lower_resume:
            problems.append("Bullet edit must quote text that already exists on the resume.")
    return problems


def humanize_tailor_patch(patch: dict) -> dict:
    out = dict(patch)
    out["summary_lines"] = [
        resume_text_service.humanize_line(str(x))
        for x in patch.get("summary_lines") or []
        if resume_text_service.humanize_line(str(x))
    ]
    if patch.get("skills_line"):
        out["skills_line"] = resume_text_service.humanize_line(str(patch["skills_line"]))
    out["skills_order"] = [
        resume_text_service.humanize_line(str(s))
        for s in patch.get("skills_order") or []
        if resume_text_service.humanize_line(str(s))
    ]
    edits = []
    for edit in patch.get("bullet_edits") or []:
        repl = resume_text_service.humanize_line(str(edit.get("replace") or ""))
        find = str(edit.get("find") or "")
        if find and repl:
            edits.append({"find": find, "replace": repl})
    out["bullet_edits"] = edits
    return out


_INTAKE_SYSTEM = (
    "Extract structured candidate data from a resume for job auto-apply. Output ONLY JSON with keys:\n"
    "first_name, last_name, middle_name, phone, current_city, linkedIn, website, headline, summary, "
    "current_title, current_company, experience_years (integer or null), has_masters (boolean), "
    "skills (string array, up to 40), preferred_roles, preferred_locations, "
    "education (array of {school, degree, field, start_year, end_year}), "
    "work_history (array of {title, company, location, start, end, summary} — summary = bullet highlights), "
    "cover_letter (120-220 words, professional, sign with name), "
    "user_information_all (plain-text facts block for AI form filling: work, education, skills).\n"
    "Rules: only resume facts; no invented employers or degrees; plain human tone; no buzzwords."
)


def _parse_intake_json(raw: str) -> dict:
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise AppError("AI_ERROR", "Could not parse intake response.", 502)
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AppError("AI_ERROR", "Intake response was not valid JSON.", 502) from exc
    if not isinstance(data, dict):
        raise AppError("AI_ERROR", "Intake response must be a JSON object.", 502)
    return data


def _normalize_education(raw) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw[:25]:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "school": str(item.get("school") or "").strip()[:255],
                "degree": str(item.get("degree") or "").strip()[:255],
                "field": str(item.get("field") or "").strip()[:255],
                "start_year": str(item.get("start_year") or "").strip()[:16],
                "end_year": str(item.get("end_year") or "").strip()[:16],
            }
        )
    return [e for e in out if any(e.values())]


def _normalize_work(raw) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw[:40]:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "title": str(item.get("title") or "").strip()[:255],
                "company": str(item.get("company") or "").strip()[:255],
                "location": str(item.get("location") or "").strip()[:255],
                "start": str(item.get("start") or "").strip()[:32],
                "end": str(item.get("end") or "").strip()[:32],
                "summary": str(item.get("summary") or "").strip()[:2000],
            }
        )
    return [e for e in out if e.get("title") or e.get("company")]


def _normalize_intake(data: dict) -> dict:
    skills = data.get("skills") or []
    if not isinstance(skills, list):
        skills = []
    skills = [str(s).strip() for s in skills if str(s).strip()][:80]
    roles = data.get("preferred_roles") or []
    if not isinstance(roles, list):
        roles = []
    roles = [str(r).strip() for r in roles if str(r).strip()][:20]
    locs = data.get("preferred_locations") or []
    if not isinstance(locs, list):
        locs = []
    locs = [str(x).strip() for x in locs if str(x).strip()][:20]
    years = data.get("experience_years")
    if years is not None:
        try:
            years = int(years)
        except (TypeError, ValueError):
            years = None
        if years is not None and (years < 0 or years > 60):
            years = None
    cover = str(data.get("cover_letter") or "").strip()[:10000]
    education = _normalize_education(data.get("education"))
    work_history = _normalize_work(data.get("work_history"))
    has_masters = bool(data.get("has_masters")) or any(
        "master" in (e.get("degree") or "").lower() or "mba" in (e.get("degree") or "").lower() for e in education
    )
    intake = {
        "first_name": str(data.get("first_name") or "").strip()[:100],
        "last_name": str(data.get("last_name") or "").strip()[:100],
        "middle_name": str(data.get("middle_name") or "").strip()[:100],
        "phone": str(data.get("phone")).strip()[:32] if data.get("phone") else None,
        "headline": str(data.get("headline") or "").strip()[:255] or None,
        "summary": str(data.get("summary") or "").strip()[:5000] or None,
        "current_title": str(data.get("current_title") or "").strip()[:255] or None,
        "current_company": str(data.get("current_company") or "").strip()[:255] or None,
        "experience_years": years,
        "skills": skills,
        "preferred_roles": roles,
        "preferred_locations": locs,
        "cover_letter": cover,
        "education": education,
        "work_history": work_history,
        "current_city": str(data.get("current_city") or "").strip()[:255] or None,
        "linkedIn": str(data.get("linkedIn") or data.get("linkedin") or "").strip()[:500] or None,
        "website": str(data.get("website") or "").strip()[:500] or None,
        "has_masters": has_masters,
    }
    uinfo = str(data.get("user_information_all") or "").strip()
    intake["user_information_all"] = uinfo[:20000] if uinfo else resume_text_service.format_user_information_block(intake)
    return intake


def _llm_intake(db: Session, text: str, *, hint_first: str, hint_last: str) -> dict:
    user_msg = json.dumps(
        {
            "account_first_name": hint_first,
            "account_last_name": hint_last,
            "resume_text": text[:20000],
        },
        ensure_ascii=False,
    )
    raw = complete(
        db,
        AiTask.RESUME_INTAKE,
        system=_INTAKE_SYSTEM,
        user=user_msg,
        feature="resume",
        temperature=0.25,
        max_tokens=3500,
    )
    return _normalize_intake(_parse_intake_json(raw))


def _blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    return False


def _merge_intake_into_user(db: Session, user: User, intake: dict) -> None:
    if _blank(user.first_name) and intake.get("first_name"):
        user.first_name = intake["first_name"]
    if _blank(user.last_name) and intake.get("last_name"):
        user.last_name = intake["last_name"]
    if user.profile is None:
        user.profile = UserProfile(user_id=user.id)
    profile = user.profile
    for key in (
        "phone",
        "headline",
        "summary",
        "current_title",
        "current_company",
        "experience_years",
        "skills",
        "preferred_roles",
        "preferred_locations",
        "education",
        "work_history",
    ):
        incoming = intake.get(key)
        current = getattr(profile, key, None)
        if key == "experience_years":
            if current is None and incoming is not None:
                profile.experience_years = incoming
            continue
        if key in ("education", "work_history"):
            if _blank(current) and incoming:
                setattr(profile, key, incoming)
            continue
        if isinstance(incoming, list):
            if _blank(current) and incoming:
                setattr(profile, key, incoming)
        elif _blank(current) and not _blank(incoming):
            setattr(profile, key, incoming)


def _intake_application_answers(intake: dict) -> dict:
    years = intake.get("experience_years")
    confidence = None
    if years is not None:
        confidence = str(min(10, max(1, int(years))))
    mapping = {
        "middle_name": intake.get("middle_name"),
        "current_city": intake.get("current_city"),
        "years_of_experience": str(years) if years is not None else None,
        "linkedIn": intake.get("linkedIn"),
        "website": intake.get("website"),
        "linkedin_headline": intake.get("headline"),
        "linkedin_summary": intake.get("summary"),
        "cover_letter": intake.get("cover_letter"),
        "recent_employer": intake.get("current_company"),
        "confidence_level": confidence,
    }
    out = {}
    for key, value in mapping.items():
        if _blank(value) or key not in APPLICATION_FIELDS:
            continue
        try:
            out[key] = validate_value(APPLICATION_FIELDS[key], value)
        except ValueError:
            continue
    return out


def _apply_intake_to_preferences(db: Session, user: User, intake: dict) -> None:
    prefs = db.scalar(select(ApplicationPreferences).where(ApplicationPreferences.user_id == user.id))
    if prefs is None:
        prefs = ApplicationPreferences(user_id=user.id, answers={})
        db.add(prefs)
        db.flush()
    answers = dict(prefs.answers or {})
    for key, value in _intake_application_answers(intake).items():
        if _blank(answers.get(key)):
            answers[key] = value
    prefs.answers = answers
    uinfo = (intake.get("user_information_all") or "").strip()
    if uinfo and _blank(prefs.user_information_all):
        prefs.user_information_all = uinfo[:20000]


def _merge_search_from_intake(db: Session, user_id: uuid.UUID, intake: dict) -> None:
    search = db.scalar(select(SearchConfig).where(SearchConfig.user_id == user_id))
    if search is None:
        return
    extra = dict(search.extra or {})
    years = intake.get("experience_years")
    if years is not None and extra.get("current_experience") is None:
        extra["current_experience"] = years
    if intake.get("has_masters") and not extra.get("did_masters"):
        extra["did_masters"] = True
    roles = intake.get("preferred_roles") or []
    if roles and not (search.keywords or []):
        search.keywords = roles[:5]
    search.extra = extra


def intake_from_resume(db: Session, user: User, resume_id: uuid.UUID, *, apply: bool = True) -> dict:
    resume = resume_service.get_resume(db, user, resume_id)
    path = resume_service.absolute_path(resume)
    text, text_source = resume_text_service.extract_text_with_source(path, resume.file_type, emphasize_ocr=True)
    if not text.strip():
        raise AppError(
            "PARSE_FAILED",
            "Could not read text from this resume. For scanned PDFs, ensure OCR dependencies are installed.",
            422,
        )

    source = "heuristic"
    intake = resume_text_service.heuristic_profile_intake(text)
    if ai_available(db, feature="resume"):
        try:
            intake = _llm_intake(db, text, hint_first=user.first_name or "", hint_last=user.last_name or "")
            source = "ai"
        except AppError:
            pass

    skills = intake.get("skills") or resume_text_service.guess_skills_from_text(text, [])
    master_count = len(skills)
    if apply:
        _merge_intake_into_user(db, user, intake)
        _apply_intake_to_preferences(db, user, intake)
        _merge_search_from_intake(db, user.id, intake)
        if skills:
            resume.master_skills = skills[:80]
            resume.subskills_by_master = resume.subskills_by_master or {}
            resume.structured_content = {
                "plain_text": text[:50000],
                "text_extraction": text_source,
            }
        db.commit()
        db.refresh(user)
        db.refresh(resume)
        master_count = len(resume.master_skills or [])

    profile_out = preferences_service.get_profile(db, user)
    prefs = preferences_service.get_application(db, user)
    cover_saved = (prefs.get("answers") or {}).get("cover_letter") or None
    return {
        "source": source,
        "text_extraction": text_source,
        "profile": profile_out,
        "cover_letter": cover_saved or intake.get("cover_letter") or None,
        "master_skills_count": master_count,
        "resume_id": str(resume_id),
    }


def analyze_master(db: Session, user: User, resume_id: uuid.UUID) -> Resume:
    resume = resume_service.get_resume(db, user, resume_id)
    path = resume_service.absolute_path(resume)
    text = resume_text_service.extract_text(path, resume.file_type)
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    profile_skills = list(profile.skills) if profile and profile.skills else []
    skills = resume_text_service.guess_skills_from_text(text, profile_skills)
    if not skills:
        raise AppError("PARSE_FAILED", "Could not detect skills. Add skills to your profile and try again.", 422)
    resume.master_skills = skills
    resume.subskills_by_master = resume.subskills_by_master or {}
    resume.structured_content = {"plain_text": text[:50000]}
    db.commit()
    db.refresh(resume)
    return resume


_TAILOR_SYSTEM = (
    "You help a candidate lightly edit their existing resume for one job. Output ONLY JSON with keys:\n"
    "summary_lines (1-4 short strings), skills_order (subset/reorder of master_skills), "
    "skills_line (one comma-separated line, how humans list tools in Word), "
    "subskills_display ({master, items[]}), jd_tools_display ({name, evidence from resume only}), "
    "bullet_edits (0-4 objects {find, replace} — find MUST be an exact substring from resume_excerpt, "
    "replace rephrases that bullet with the same facts/metrics, weaving JD keywords naturally).\n"
    "Rules:\n"
    "- Sound like the candidate wrote it in Word: plain verbs, varied sentence length, no marketing tone.\n"
    "- Match the voice, tense, and formatting habits in resume_excerpt.\n"
    "- Never invent employers, titles, dates, degrees, certifications, or tools not evidenced on the resume.\n"
    "- Do NOT use buzzwords (results-driven, passionate, leverage, synergy, cutting-edge, team player, etc.).\n"
    "- Do NOT mention AI, tailoring, ATS, or the job description explicitly in visible text.\n"
    "- Prefer small bullet tweaks over a brand-new summary; keep edits minimal and believable.\n"
    "- Master skills list is fixed — only reorder/emphasize; evidence quotes must appear in resume_excerpt."
)


def _llm_tailor(db: Session, *, master_skills: list[str], resume_text: str, jd: str) -> dict:
    user = json.dumps(
        {"master_skills": master_skills, "resume_excerpt": resume_text[:12000], "job_description": jd[:12000]},
        ensure_ascii=False,
    )
    raw = complete(
        db,
        AiTask.RESUME_TAILOR,
        system=_TAILOR_SYSTEM,
        user=user,
        feature="resume",
        temperature=0.55,
        max_tokens=2500,
    )
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise AppError("AI_ERROR", "Could not parse tailor response.", 502)
    try:
        patch = json.loads(raw[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AppError("AI_ERROR", "Tailor response was not valid JSON.", 502) from exc
    return humanize_tailor_patch(patch)


def preview(db: Session, user: User, *, resume_id: uuid.UUID, job_description: str) -> dict:
    if not ai_available(db, feature="resume"):
        raise AppError("AI_DISABLED", "Platform AI is not enabled for resume features.", 503)
    resume = resume_service.get_resume(db, user, resume_id)
    masters = list(resume.master_skills or [])
    if not masters:
        raise AppError("MASTER_REQUIRED", "Analyze master skills on this resume first.", 422)
    path = resume_service.absolute_path(resume)
    text = resume_text_service.extract_text(path, resume.file_type)
    score, missing = match_score(masters, text, job_description)
    if score < _GATE_MIN:
        return {
            "gate_passed": False,
            "match_score": score,
            "missing_keywords": missing,
            "fit_score": None,
            "patch": None,
        }
    patch = _llm_tailor(db, master_skills=masters, resume_text=text, jd=job_description)
    problems = validate_tailor_patch(masters, job_description, text, patch)
    fit = _ats_score(masters, text, job_description, patch)
    refine = 0
    while fit < _FIT_TARGET and refine < _MAX_REFINE and not problems:
        refine += 1
        patch = _llm_tailor(db, master_skills=masters, resume_text=text + "\n" + jd_keywords_hint(job_description, missing), jd=job_description)
        problems = validate_tailor_patch(masters, job_description, text, patch)
        fit = _ats_score(masters, text, job_description, patch)
    return {
        "gate_passed": True,
        "match_score": score,
        "missing_keywords": missing,
        "fit_score": fit,
        "validation_warnings": problems,
        "patch": patch,
        "disclaimer": "Fit score is an internal estimate, not a guarantee of ATS or recruiter acceptance.",
    }


def jd_keywords_hint(jd: str, missing: list[str]) -> str:
    return "Emphasize evidenced keywords: " + ", ".join(missing[:15])


def _name_segment(value: str, *, fallback: str = "") -> str:
    text = re.sub(r"\s+", " ", (value or "").strip()).replace("_", " ")
    return (text or fallback)[:120]


def _experience_years_label(db: Session, user_id: uuid.UUID) -> str:
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
    if profile is not None and profile.experience_years is not None:
        n = profile.experience_years
        suffix = "year" if n == 1 else "years"
        return f"{n} {suffix}"
    prefs = db.scalar(select(ApplicationPreferences).where(ApplicationPreferences.user_id == user_id))
    raw = (prefs.answers or {}).get("years_of_experience") if prefs else None
    if raw is not None and str(raw).strip():
        text = str(raw).strip()
        try:
            n = int(text.split(".")[0])
            suffix = "year" if n == 1 else "years"
            return f"{n} {suffix}"
        except ValueError:
            return text[:40]
    return "0 years"


def build_resume_version_name(
    db: Session,
    user: User,
    *,
    master_skills: list[str],
    patch: dict | None = None,
) -> str:
    """Display name: {name}_{main skill}_{years of experience}."""
    person = _name_segment(" ".join(p for p in (user.first_name, user.last_name) if p), fallback="Resume")
    order = (patch or {}).get("skills_order") or []
    main_skill = _name_segment(str(order[0]), fallback="") if order else ""
    if not main_skill and master_skills:
        main_skill = _name_segment(str(master_skills[0]), fallback="General")
    if not main_skill:
        main_skill = "General"
    years = _experience_years_label(db, user.id)
    return f"{person}_{main_skill}_{years}"[:255]


def render_docx(source_path: Path, patch: dict, out_path: Path, *, resume_text: str, template_id: str) -> None:
    """Edit the source layout in place; strip doc metadata that flags automated authoring."""
    resume_text_service.render_tailored_docx(
        source_path, patch, out_path, resume_text=resume_text, template_id=template_id,
    )


async def tailor_and_save(
    db: Session,
    user: User,
    *,
    resume_id: uuid.UUID,
    job_description: str,
    job_id: str = "",
    template_id: str | None = None,
    application_id: uuid.UUID | None = None,
) -> Resume:
    preview_data = preview(db, user, resume_id=resume_id, job_description=job_description)
    if not preview_data.get("gate_passed"):
        raise AppError("GATE_FAILED", f"Match score {preview_data['match_score']}% is below {_GATE_MIN}%.", 422)
    patch = preview_data.get("patch") or {}
    source = resume_service.get_resume(db, user, resume_id)
    masters = list(source.master_skills or [])
    version_name = build_resume_version_name(db, user, master_skills=masters, patch=patch)
    src_path = resume_service.absolute_path(source)
    resume_text = resume_text_service.extract_text(src_path, source.file_type)
    tmp = src_path.parent / f"tailored-{uuid.uuid4().hex}.docx"
    style_id = template_id or preferred_template_for_user(db, user)
    render_docx(src_path, patch, tmp, resume_text=resume_text, template_id=style_id)
    data = tmp.read_bytes()
    file_stub = re.sub(r"[^\w\s.-]+", "", version_name).strip().replace(" ", "_") or "resume"
    upload = UploadFile(filename=f"{file_stub}.docx", file=io.BytesIO(data))
    new_resume = await resume_service.upload_resume(db, user, upload, name=version_name, counts_against_plan=False)
    new_resume.ai_metadata = {
        "generated_by": "ai",
        "job_id": job_id,
        "match_score": preview_data.get("match_score"),
        "fit_score": preview_data.get("fit_score"),
        "source_resume_id": str(resume_id),
        "template_id": style_id,
        "template_name": get_template(style_id).name,
    }
    target_app = application_id
    if target_app is None and job_id:
        linked = application_service.application_for_external_job(db, user.id, job_id)
        target_app = linked.id if linked else None
    if target_app is not None:
        application_service.attach_generated_resume(db, user.id, target_app, new_resume.id)
    db.commit()
    db.refresh(new_resume)
    try:
        tmp.unlink(missing_ok=True)
    except OSError:
        pass
    return new_resume
