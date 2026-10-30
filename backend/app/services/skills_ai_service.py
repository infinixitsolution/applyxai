"""Fill Master Profile IT / key skills from the default resume. Do not invent tools."""

from __future__ import annotations

import copy
import json
import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.app.core.errors import AppError
from backend.app.core.profile_taxonomies import SKILL_CATEGORIES
from backend.app.models import ApplicationPreferences, User
from backend.app.services import master_profile_service, resume_service, resume_text_service, run_config_service
from backend.app.services.ai_service import AiTask, ai_available, complete

_MAX_SKILLS = 40
_DEFAULT_CATEGORY = "Technical / IT skills"

_CATEGORY_HINTS: list[tuple[str, tuple[str, ...]]] = [
    ("Business applications", ("servicenow", "itsm", "itil", "catalog", "cmdb", "glide", "flow designer", "sla")),
    ("Databases", ("sql", "mysql", "postgres", "oracle", "mongodb", "database")),
    ("Programming languages", ("javascript", "python", "java", "typescript", "html", "css")),
    ("Cloud and DevOps tools", ("aws", "azure", "gcp", "docker", "kubernetes", "jenkins", "git", "linux", "terraform")),
    ("Frameworks and libraries", ("react", "angular", "spring", "node", "django", "flask")),
    ("Soft skills", ("communication", "leadership", "teamwork")),
]


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _clip(text: str, *, limit: int) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())[:limit].rstrip()


def categorize_skill(name: str) -> str:
    blob = (name or "").lower()
    for category, hints in _CATEGORY_HINTS:
        if any(h in blob for h in hints):
            return category
    if any(w in blob for w in ("incident", "problem", "change", "request", "knowledge", "workflow", "acl", "notification")):
        return "Business applications"
    return _DEFAULT_CATEGORY


def category_allowed(label: str) -> bool:
    return label in SKILL_CATEGORIES


def resume_mentions(name: str, resume_text: str) -> bool:
    """True when this skill is written on the resume (no invented tools)."""
    blob = (resume_text or "").lower()
    token = (name or "").strip()
    if not token or not blob:
        return False
    low = token.lower()
    if re.search(rf"\b{re.escape(low)}\b", blob):
        return True
    words = [w for w in re.findall(r"[a-z0-9+#]+", low) if w not in {"and", "of", "the", "for", "with"}]
    if len(words) >= 2 and all(re.search(rf"\b{re.escape(w)}\b", blob) for w in words):
        return True
    compact = _compact(token)
    hay = _compact(blob)
    return bool(compact and len(compact) >= 3 and compact in hay)


def skills_from_resume(resume_text: str, extra: list[str] | None = None) -> list[dict]:
    """Parse IT skills from the resume Skills section; keep extra names only if they appear in the text."""
    names = resume_text_service.guess_skills_from_text(resume_text, [])
    for raw in extra or []:
        token = resume_text_service.clean_skill_token(raw)
        if token and resume_mentions(token, resume_text) and token.lower() not in {n.lower() for n in names}:
            names.append(token)
    rows: list[dict] = []
    seen: set[str] = set()
    for name in names:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append(_row(name, categorize_skill(name)))
        if len(rows) >= _MAX_SKILLS:
            break
    return rows


def _row(name: str, category: str, *, years: str = "") -> dict:
    cat = category if category_allowed(category) else _DEFAULT_CATEGORY
    return {
        "id": str(uuid.uuid4()),
        "name": _clip(name, limit=80),
        "category": cat,
        "years": _clip(years, limit=16),
        "proficiency": "",
        "description": "",
    }


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
        raise AppError("AI_PARSE_ERROR", "Could not parse AI skills.", 502) from exc
    return data if isinstance(data, dict) else {}


def _llm_skills(db: Session, *, resume_text: str) -> list[dict]:
    cats = ", ".join(SKILL_CATEGORIES)
    system = (
        "Extract IT and professional skills that are written on this resume. Output ONLY JSON "
        '{"skills":[{"name","category"}]}. '
        f"category must be one of: {cats}. "
        "Do not add tools, cloud platforms, programming languages, or products that are not written. "
        "Skip spoken languages, school names, cities, degrees, and section headers. "
        "Use standard names (Incident Management, not Incident). Prefer 12-30 distinct skills."
    )
    raw = complete(
        db,
        AiTask.APP_ANSWER,
        system=system,
        user=(resume_text or "")[:9000],
        feature="applications",
        temperature=0.1,
        max_tokens=1200,
    )
    data = _parse_json(raw)
    rows = data.get("skills") if isinstance(data.get("skills"), list) else []
    out: list[dict] = []
    seen: set[str] = set()
    for item in rows:
        if isinstance(item, str):
            name, category = item, ""
        elif isinstance(item, dict):
            name, category = str(item.get("name") or ""), str(item.get("category") or "")
        else:
            continue
        token = resume_text_service.clean_skill_token(name)
        if not token or not resume_mentions(token, resume_text):
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(_row(token, category or categorize_skill(token)))
        if len(out) >= _MAX_SKILLS:
            break
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


def _names(rows: list[dict]) -> list[str]:
    out: list[str] = []
    for row in rows:
        name = str(row.get("name") or "").strip()
        if name and name not in out:
            out.append(name)
    return out


def fill_skills_from_resume(db: Session, user: User) -> dict:
    if user.profile is None:
        raise AppError("VALIDATION_ERROR", "Create a profile first.", 422)
    profile = user.profile
    resume_text = _resume_text(db, user.id)
    existing = [str(s).strip() for s in (profile.skills or []) if str(s).strip()]
    source = "heuristic"
    if resume_text:
        rows = skills_from_resume(resume_text, extra=existing)
        if ai_available(db, feature="applications") or ai_available(db, feature="resume"):
            try:
                ai_rows = _llm_skills(db, resume_text=resume_text)
                if ai_rows:
                    merged: list[dict] = []
                    seen: set[str] = set()
                    for row in ai_rows + rows:
                        key = str(row.get("name") or "").lower()
                        if not key or key in seen:
                            continue
                        seen.add(key)
                        merged.append(row)
                        if len(merged) >= _MAX_SKILLS:
                            break
                    rows = merged
                    source = "ai"
            except AppError:
                pass
    else:
        rows = [_row(n, categorize_skill(n)) for n in existing[:_MAX_SKILLS]]
        if not rows:
            raise AppError("PARSE_FAILED", "Upload a default resume so skills can be filled from it.", 422)

    master = copy.deepcopy(master_profile_service.ensure_master_data(profile))
    master["skills"] = rows
    profile.master_data = master
    profile.skills = _names(rows)
    flag_modified(profile, "master_data")
    flag_modified(profile, "skills")

    resume = run_config_service.default_resume(db, user.id)
    if resume is not None and profile.skills:
        resume.master_skills = list(profile.skills)[:80]
        resume.subskills_by_master = resume.subskills_by_master or {}
        flag_modified(resume, "master_skills")

    prefs = db.scalar(select(ApplicationPreferences).where(ApplicationPreferences.user_id == user.id))
    master_profile_service._sync_structured_to_engine(profile, user, prefs)
    db.commit()
    db.refresh(user)
    payload = master_profile_service.master_profile_payload(db, user)
    return {
        "source": source,
        "skills": list(profile.skills or []),
        "rows": rows,
        "profile": payload,
    }
