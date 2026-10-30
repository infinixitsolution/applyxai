"""Suggest preferred job roles and locations from the Master Profile."""

from __future__ import annotations

import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.models import ApplicationPreferences, SearchConfig, User
from backend.app.services import master_profile_service
from backend.app.services.ai_service import AiTask, ai_available, complete

_ROLE_EXPAND = {
    "devops": ["DevOps Engineer", "Junior DevOps Engineer", "Cloud Engineer", "Site Reliability Engineer", "Platform Engineer"],
    "sre": ["Site Reliability Engineer", "DevOps Engineer", "Platform Engineer"],
    "cloud": ["Cloud Engineer", "AWS Engineer", "DevOps Engineer"],
    "aws": ["AWS Engineer", "Cloud Engineer", "DevOps Engineer"],
    "azure": ["Azure Engineer", "Cloud Engineer", "DevOps Engineer"],
    "kubernetes": ["Kubernetes Engineer", "DevOps Engineer", "Platform Engineer"],
    "kubernet": ["Kubernetes Engineer", "DevOps Engineer"],
    "servicenow": ["ServiceNow Administrator", "ServiceNow Developer", "ITSM Analyst"],
    "itsm": ["ITSM Analyst", "ServiceNow Administrator"],
    "software": ["Software Engineer", "Backend Developer"],
    "developer": ["Software Engineer", "Backend Developer"],
    "engineer": ["Software Engineer"],
    "data": ["Data Engineer", "Data Analyst"],
    "python": ["Python Developer", "Backend Developer"],
}

_CITY_EXPAND = {
    "bangalore": ["Bangalore", "Bengaluru", "Remote"],
    "bengaluru": ["Bengaluru", "Bangalore", "Remote"],
    "mumbai": ["Mumbai", "Navi Mumbai", "Remote"],
    "delhi": ["Delhi", "NCR", "Gurugram", "Noida", "Remote"],
    "hyderabad": ["Hyderabad", "Remote"],
    "pune": ["Pune", "Remote"],
    "chennai": ["Chennai", "Remote"],
    "kolkata": ["Kolkata", "Remote"],
    "noida": ["Noida", "NCR", "Remote"],
    "gurgaon": ["Gurugram", "NCR", "Remote"],
    "gurugram": ["Gurugram", "NCR", "Remote"],
}


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _uniq(items: list[str], *, limit: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in items:
        label = " ".join(str(raw or "").split())
        key = _compact(label)
        if not label or key in seen:
            continue
        seen.add(key)
        out.append(label[:80])
        if len(out) >= limit:
            break
    return out


def _tokens(*parts: str) -> list[str]:
    blob = " ".join(p for p in parts if p).lower()
    return re.findall(r"[a-z][a-z0-9+#.]{1,32}", blob)


def heuristic_career_preferences(
    *,
    title: str = "",
    headline: str = "",
    skills: list[str] | None = None,
    roles: list[str] | None = None,
    locations: list[str] | None = None,
    city: str = "",
) -> dict[str, list[str]]:
    seed_roles = list(roles or [])
    expanded: list[str] = list(seed_roles)
    if title.strip():
        expanded.insert(0, title.strip())
    for token in _tokens(title, headline, " ".join(skills or []), " ".join(seed_roles)):
        expanded.extend(_ROLE_EXPAND.get(token, []))
    seed_locs = list(locations or [])
    loc_out: list[str] = list(seed_locs)
    if city.strip():
        loc_out.insert(0, city.strip())
    for token in _tokens(*seed_locs, city):
        loc_out.extend(_CITY_EXPAND.get(token, []))
    if loc_out and "Remote" not in loc_out:
        loc_out.append("Remote")
    return {
        "preferred_roles": _uniq(expanded, limit=12),
        "preferred_locations": _uniq(loc_out, limit=8),
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
        raise AppError("AI_PARSE_ERROR", "Could not parse AI career suggestions.", 502) from exc
    return data if isinstance(data, dict) else {}


def _llm_career(db: Session, payload: dict) -> dict[str, list[str]]:
    system = (
        "Suggest job-search preferences for this candidate. Output ONLY JSON with keys "
        "preferred_roles (6-10 specific job titles), preferred_locations (3-6 cities or Remote), "
        "desired_industries (1-3 short labels). Keep their existing tags. "
        "Only titles that match their skills, education, and title. "
        "If experience_years is 0 or 1, prefer junior/fresher/associate titles. Do not invent employers."
    )
    raw = complete(
        db,
        AiTask.APP_ANSWER,
        system=system,
        user=json.dumps(payload, ensure_ascii=False)[:8000],
        feature="applications",
        temperature=0.3,
        max_tokens=700,
    )
    data = _parse_json(raw)
    roles = data.get("preferred_roles") if isinstance(data.get("preferred_roles"), list) else []
    locs = data.get("preferred_locations") if isinstance(data.get("preferred_locations"), list) else []
    industries = data.get("desired_industries") if isinstance(data.get("desired_industries"), list) else []
    return {
        "preferred_roles": [str(x).strip() for x in roles if str(x).strip()],
        "preferred_locations": [str(x).strip() for x in locs if str(x).strip()],
        "desired_industries": [str(x).strip() for x in industries if str(x).strip()][:3],
    }


def enhance_career_preferences(db: Session, user: User) -> dict:
    if user.profile is None:
        raise AppError("VALIDATION_ERROR", "Create a profile first.", 422)
    profile = user.profile
    master = master_profile_service.ensure_master_data(profile)
    personal = master.get("personal") or {}
    career = dict(master.get("career") or {})
    city = str(personal.get("city") or "")
    existing_roles = list(profile.preferred_roles or []) or list(career.get("preferred_roles") or [])
    existing_locs = list(profile.preferred_locations or []) or list(career.get("preferred_locations") or [])
    skills = list(profile.skills or [])
    suggested = heuristic_career_preferences(
        title=profile.current_title or "",
        headline=profile.headline or "",
        skills=skills,
        roles=existing_roles,
        locations=existing_locs,
        city=city,
    )
    source = "heuristic"
    industries: list[str] = list(career.get("desired_industries") or []) if isinstance(career.get("desired_industries"), list) else []
    if ai_available(db, feature="applications") or ai_available(db, feature="profile_sync"):
        try:
            ai = _llm_career(
                db,
                {
                    "current_title": profile.current_title,
                    "headline": profile.headline,
                    "experience_years": profile.experience_years,
                    "skills": skills[:40],
                    "education": (profile.education or [])[:5],
                    "preferred_roles": existing_roles,
                    "preferred_locations": existing_locs,
                    "city": city,
                },
            )
            suggested["preferred_roles"] = _uniq(existing_roles + ai["preferred_roles"] + suggested["preferred_roles"], limit=12)
            suggested["preferred_locations"] = _uniq(existing_locs + ai["preferred_locations"] + suggested["preferred_locations"], limit=8)
            if ai.get("desired_industries"):
                industries = _uniq(industries + ai["desired_industries"], limit=3)
            source = "ai"
        except AppError:
            pass

    profile.preferred_roles = suggested["preferred_roles"]
    profile.preferred_locations = suggested["preferred_locations"]
    career["preferred_roles"] = suggested["preferred_roles"]
    career["preferred_locations"] = suggested["preferred_locations"]
    if industries:
        career["desired_industries"] = industries
    master["career"] = career
    profile.master_data = master

    prefs = db.scalar(select(ApplicationPreferences).where(ApplicationPreferences.user_id == user.id))
    master_profile_service._sync_structured_to_engine(profile, user, prefs)
    search = db.scalar(select(SearchConfig).where(SearchConfig.user_id == user.id))
    if search is not None and not (search.keywords or []) and suggested["preferred_roles"]:
        search.keywords = suggested["preferred_roles"][:5]
    db.commit()
    db.refresh(user)
    payload = master_profile_service.master_profile_payload(db, user)
    return {
        "source": source,
        "preferred_roles": suggested["preferred_roles"],
        "preferred_locations": suggested["preferred_locations"],
        "desired_industries": industries,
        "profile": payload,
    }
