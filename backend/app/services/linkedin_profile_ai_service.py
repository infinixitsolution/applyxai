"""AI drafts for Master Profile / LinkedIn-oriented text."""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.models import ApplicationPreferences, User
from backend.app.services import master_profile_service, preferences_service
from backend.app.services.ai_service import AiTask, ai_available, complete
from backend.app.services.application_context import build_context
from backend.app.services.linkedin_profile_sync_service import build_snapshot

_MAX_HEADLINE = 220
_MAX_ABOUT = 2600


def _parse_json(raw: str) -> dict:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AppError("AI_PARSE_ERROR", "Could not parse AI response.", 502) from exc
    return data if isinstance(data, dict) else {}


def generate_completion_draft(db: Session, user: User) -> dict:
    if not ai_available(db, feature="profile_sync"):
        raise AppError("AI_DISABLED", "Profile sync AI is not enabled. Ask an admin to turn on Platform AI → Profile sync.", 503)
    snapshot = build_snapshot(db, user)
    master = master_profile_service.ensure_master_data(user.profile)
    context = build_context(db, user.id, include_default_resume=True)
    system = (
        "You help candidates complete a professional profile for job applications and LinkedIn. "
        "Use ONLY facts from the context. Do not invent employers, degrees, dates, or credentials. "
        "Return strict JSON with keys: headline (string), about (string), skills (array of strings), "
        "experience_bullets (array of {company, title, bullets: string[]}). "
        "Keep headline under 220 characters and about under 2500 characters."
    )
    user_msg = (
        f"{context}\n\nMaster profile JSON (abbreviated):\n"
        f"{json.dumps({'master': master, 'snapshot': snapshot}, default=str)[:12000]}"
    )
    raw = complete(db, AiTask.APP_ANSWER, system=system, user=user_msg, feature="profile_sync", max_tokens=2000)
    draft = _parse_json(raw)
    headline = str(draft.get("headline") or "")[:_MAX_HEADLINE]
    about = str(draft.get("about") or "")[:_MAX_ABOUT]
    skills_raw = draft.get("skills") if isinstance(draft.get("skills"), list) else []
    skills = [str(s).strip() for s in skills_raw if str(s).strip()][:50]
    bullets = draft.get("experience_bullets") if isinstance(draft.get("experience_bullets"), list) else []
    return {
        "headline": headline,
        "about": about,
        "skills": skills,
        "experience_bullets": bullets[:20],
        "unchanged": not any([headline, about, skills, bullets]),
    }


def apply_ai_draft(db: Session, user: User, draft: dict) -> dict:
    if not isinstance(draft, dict):
        raise AppError("VALIDATION_ERROR", "draft must be an object", 422)
    profile = user.profile
    if profile is None:
        raise AppError("VALIDATION_ERROR", "Profile not found", 422)
    if draft.get("headline"):
        profile.headline = str(draft["headline"])[:255]
    if draft.get("about"):
        profile.summary = str(draft["about"])[:10000]
    skills = draft.get("skills")
    if isinstance(skills, list) and skills:
        master = master_profile_service.ensure_master_data(profile)
        existing = master.get("skills") or []
        names = {str(x.get("name") if isinstance(x, dict) else x).lower() for x in existing if x}
        for s in skills:
            name = str(s).strip()
            if name.lower() not in names:
                existing.append({"id": name, "name": name, "category": ""})
                names.add(name.lower())
        master["skills"] = existing
        profile.master_data = master
        profile.skills = [str(s.get("name") if isinstance(s, dict) else s) for s in existing][:100]
    db.flush()
    prefs = db.scalar(select(ApplicationPreferences).where(ApplicationPreferences.user_id == user.id))
    master_profile_service._sync_structured_to_engine(profile, user, prefs)
    db.commit()
    db.refresh(user)
    return master_profile_service.master_profile_payload(db, user)
