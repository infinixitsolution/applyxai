"""Extended master profile storage, completion, and sync to engine application answers."""

from __future__ import annotations

import copy
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.profile_taxonomies import COMMON_ANSWER_TEMPLATES
from backend.app.models import ApplicationPreferences, User, UserProfile
from backend.app.services.engine_fields import PROFILE_ANSWER_FIELDS

_SECTION_KEYS = (
    "personal",
    "professional",
    "education_extended",
    "employment_extended",
    "skills",
    "projects",
    "accomplishments",
    "career",
    "diversity",
    "common_answers",
)

_COMPLETION_WEIGHTS = {
    "personal": 12,
    "photo": 5,
    "professional": 15,
    "education": 10,
    "employment": 10,
    "skills": 10,
    "projects": 8,
    "accomplishments": 8,
    "career": 12,
    "common_answers": 10,
}

_MISSING_META = {
    "personal": {"hint": "Add your name and a phone number.", "ai": False},
    "photo": {"hint": "Upload a profile photo. AI cannot add this.", "ai": False},
    "professional": {"hint": "AI can write headline and summary from your resume.", "ai": True},
    "education": {"hint": "AI can fill schools and degrees from your resume.", "ai": True},
    "employment": {"hint": "AI fills jobs from the resume, or marks Fresher when there is no employer.", "ai": True},
    "skills": {"hint": "AI can list skills from your resume.", "ai": True},
    "projects": {"hint": "AI can add academic or work projects from your resume.", "ai": True},
    "accomplishments": {"hint": "Optional awards, publications, and links.", "ai": False},
    "career": {"hint": "AI can expand preferred roles and locations.", "ai": True},
    "common_answers": {"hint": "AI can draft reusable application answers from your resume.", "ai": True},
}

_STANDARD_HUMAN_PATTERNS = (
    "current salary",
    "current ctc",
    "expected salary",
    "expected ctc",
    "notice period",
    "when can you join",
    "years of experience",
    "years of professional experience",
    "how many years",
    "legally authorized",
    "visa sponsorship",
    "phone number",
    "email address",
    "first name",
    "last name",
)

_STANDARD_EXPERIENCE_RE = re.compile(
    r"(total\s+)?(additional\s+)?months\s+of\s+experience|(total\s+)?years\s+of\s+(professional\s+)?experience",
    re.I,
)


def _empty_master() -> dict:
    list_sections = {"skills", "projects", "common_answers"}
    return {k: [] if k in list_sections else {} for k in _SECTION_KEYS}


def _deep_merge(base: dict, patch: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def ensure_master_data(profile: UserProfile | None) -> dict:
    if profile is None:
        return _empty_master()
    raw = profile.master_data if isinstance(profile.master_data, dict) else {}
    merged = _empty_master()
    for key in _SECTION_KEYS:
        val = raw.get(key)
        if key in ("skills", "projects", "common_answers") and isinstance(val, list):
            merged[key] = val
        elif isinstance(val, dict):
            merged[key] = {**merged.get(key, {}), **val}
    return merged


def _seed_common_answers(master: dict) -> None:
    existing = {str(a.get("key") or ""): a for a in master.get("common_answers") or [] if isinstance(a, dict)}
    for tpl in COMMON_ANSWER_TEMPLATES:
        key = tpl["key"]
        if key not in existing:
            existing[key] = {
                "id": str(uuid.uuid4()),
                "key": key,
                "question": tpl["question"],
                "answer": "",
                "answer_type": "text",
                "category": tpl.get("category", ""),
                "verified": False,
                "profile_field": tpl.get("profile_field"),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": None,
            }
    master["common_answers"] = list(existing.values())


def _sync_structured_to_engine(profile: UserProfile, user: User, prefs: ApplicationPreferences | None) -> None:
    """Push canonical master profile values into application_preferences.answers for the automation engine."""
    if prefs is None:
        return
    master = ensure_master_data(profile)
    personal = master.get("personal") or {}
    professional = master.get("professional") or {}
    career = master.get("career") or {}
    diversity = master.get("diversity") or {}
    answers = dict(prefs.answers or {})

    def put(key: str, value: Any) -> None:
        if value is None or value == "":
            return
        if key in PROFILE_ANSWER_FIELDS:
            answers[key] = value

    if personal.get("street"):
        put("street", str(personal["street"]).strip())
    if personal.get("state"):
        put("state", str(personal["state"]).strip())
    if personal.get("postal_code"):
        put("zipcode", str(personal["postal_code"]).strip())
    if personal.get("country"):
        put("country", str(personal["country"]).strip())
    if personal.get("city"):
        put("current_city", str(personal["city"]).strip())
    if personal.get("gender"):
        put("gender", personal["gender"])
    if diversity.get("disability_status"):
        put("disability_status", diversity["disability_status"])
    if diversity.get("veteran_status"):
        put("veteran_status", diversity["veteran_status"])
    if personal.get("ethnicity"):
        put("ethnicity", personal["ethnicity"])

    if professional.get("current_ctc") is not None:
        put("current_ctc", int(professional["current_ctc"]))
    if professional.get("expected_ctc") is not None:
        put("desired_salary", int(professional["expected_ctc"]))
    if professional.get("notice_period_days") is not None:
        put("notice_period", int(professional["notice_period_days"]))
    if profile.experience_years is not None:
        put("years_of_experience", str(profile.experience_years))
    if professional.get("confidence_level"):
        put("confidence_level", str(professional["confidence_level"]).strip())
    if profile.current_company:
        put("recent_employer", profile.current_company)
    if profile.headline:
        put("linkedin_headline", profile.headline)
    if profile.summary:
        put("linkedin_summary", profile.summary)

    for item in master.get("common_answers") or []:
        if not isinstance(item, dict):
            continue
        pf = item.get("profile_field")
        ans = str(item.get("answer") or "").strip()
        if pf == "current_ctc" and professional.get("current_ctc") is not None and not item.get("verified"):
            item["answer"] = str(professional["current_ctc"])
        elif pf == "expected_ctc" and professional.get("expected_ctc") is not None and not item.get("verified"):
            item["answer"] = str(professional["expected_ctc"])
        elif pf == "notice_period_days" and professional.get("notice_period_days") is not None and not item.get("verified"):
            item["answer"] = str(professional["notice_period_days"])
        elif pf == "availability" and professional.get("availability_type") and not item.get("verified"):
            item["answer"] = str(professional.get("availability_description") or professional["availability_type"])
        elif ans and not item.get("verified"):
            continue
        elif ans and item.get("verified"):
            key = item.get("key") or ""
            if key == "work_auth" and "legally_authorized" in PROFILE_ANSWER_FIELDS:
                if ans.lower() in ("yes", "no"):
                    put("legally_authorized", ans.capitalize())
            if key == "visa_sponsor" and "require_visa" in PROFILE_ANSWER_FIELDS:
                if ans.lower() in ("yes", "no"):
                    put("require_visa", ans.capitalize())

    if career.get("linkedin_url"):
        put("linkedIn", str(career["linkedin_url"]).strip())
    if career.get("portfolio_url"):
        put("website", str(career["portfolio_url"]).strip())
    acc = master.get("accomplishments") if isinstance(master.get("accomplishments"), dict) else {}
    for link in acc.get("links") or []:
        if not isinstance(link, dict):
            continue
        url = str(link.get("url") or "").strip()
        if url and not answers.get("website"):
            put("website", url)
            break
    extras = []
    for award in acc.get("awards") or []:
        if isinstance(award, dict) and str(award.get("title") or "").strip():
            extras.append(str(award.get("title")).strip())
    for pub in acc.get("publications") or []:
        if isinstance(pub, dict) and str(pub.get("title") or "").strip():
            extras.append(str(pub.get("title")).strip())
    notes = str(acc.get("notes") or "").strip()
    if extras or notes:
        blob = answers.get("user_information_all") or ""
        extra_text = "Accomplishments: " + "; ".join(extras[:12])
        if notes:
            extra_text = extra_text + (". " if extras else "") + notes
        if extra_text not in str(blob):
            put("user_information_all", (str(blob).rstrip() + "\n\n" + extra_text).strip() if blob else extra_text)

    prefs.answers = answers
    profile.master_data = master


def _is_standard_human_pattern(pattern: str) -> bool:
    low = (pattern or "").lower()
    if any(p in low for p in _STANDARD_HUMAN_PATTERNS):
        return True
    return bool(_STANDARD_EXPERIENCE_RE.search(low))


def migrate_legacy_master(db: Session, user: User, profile: UserProfile, prefs: ApplicationPreferences | None) -> bool:
    """One-time idempotent migration from flat application answers into master sections."""
    if profile.master_migrated_at is not None:
        return False
    master = ensure_master_data(profile)
    _seed_common_answers(master)

    if prefs is not None:
        answers = prefs.answers or {}
        professional = master.setdefault("professional", {})
        personal = master.setdefault("personal", {})
        career = master.setdefault("career", {})
        diversity = master.setdefault("diversity", {})

        if answers.get("current_ctc") is not None and professional.get("current_ctc") is None:
            professional["current_ctc"] = answers["current_ctc"]
        if answers.get("desired_salary") is not None and professional.get("expected_ctc") is None:
            professional["expected_ctc"] = answers["desired_salary"]
        if answers.get("notice_period") is not None and professional.get("notice_period_days") is None:
            professional["notice_period_days"] = answers["notice_period"]
        for eng, personal_key in (
            ("street", "street"),
            ("state", "state"),
            ("zipcode", "postal_code"),
            ("country", "country"),
            ("current_city", "city"),
            ("gender", "gender"),
            ("ethnicity", "ethnicity"),
        ):
            if answers.get(eng) and not personal.get(personal_key):
                personal[personal_key] = answers[eng]
        if answers.get("disability_status"):
            diversity["disability_status"] = answers["disability_status"]
        if answers.get("veteran_status"):
            diversity["veteran_status"] = answers["veteran_status"]
        if answers.get("linkedIn"):
            career["linkedin_url"] = answers["linkedIn"]
        if answers.get("website"):
            career["portfolio_url"] = answers["website"]

        if answers.get("linkedin_summary") and not profile.summary:
            profile.summary = str(answers["linkedin_summary"])
        if answers.get("linkedin_headline") and not profile.headline:
            profile.headline = str(answers["linkedin_headline"])

        human = list(prefs.human_questions or [])
        cleaned = []
        for row in human:
            if not isinstance(row, dict):
                continue
            pattern = str(row.get("pattern") or "")
            if _is_standard_human_pattern(pattern):
                continue
            if not row.get("created_at"):
                row["created_at"] = datetime.now(timezone.utc).isoformat()
            row.setdefault("verified", bool(row.get("locked")))
            row.setdefault("usage_count", 0)
            row.setdefault("input_type", (row.get("field_types") or ["text"])[0])
            row.setdefault("normalized_pattern", pattern.strip().lower())
            cleaned.append(row)
        prefs.human_questions = cleaned

    profile.master_data = master
    profile.master_migrated_at = datetime.now(timezone.utc)
    _sync_structured_to_engine(profile, user, prefs)
    return True


def update_master_section(db: Session, user: User, section: str, payload: dict) -> dict:
    if section not in _SECTION_KEYS:
        raise ValueError(f"Unknown section: {section}")
    if user.profile is None:
        user.profile = UserProfile(user_id=user.id)
        db.add(user.profile)
    profile = user.profile
    master = ensure_master_data(profile)
    if section in ("skills", "projects", "common_answers"):
        if not isinstance(payload, list):
            raise ValueError("Expected a list for this section")
        master[section] = payload
        if section == "skills":
            profile.skills = [
                str(item.get("name") if isinstance(item, dict) else item or "").strip()
                for item in payload
                if str(item.get("name") if isinstance(item, dict) else item or "").strip()
            ][:80]
    else:
        if not isinstance(payload, dict):
            raise ValueError("Expected an object for this section")
        master[section] = _deep_merge(master.get(section) or {}, payload)
    profile.master_data = master
    if section == "career" and isinstance(payload, dict):
        roles = payload.get("preferred_roles")
        locs = payload.get("preferred_locations")
        if isinstance(roles, list):
            profile.preferred_roles = [str(x).strip() for x in roles if str(x).strip()][:20]
        if isinstance(locs, list):
            profile.preferred_locations = [str(x).strip() for x in locs if str(x).strip()][:20]
    from backend.app.services.preferences_service import _application_row

    prefs = _application_row(db, user)
    _sync_structured_to_engine(profile, user, prefs)
    db.commit()
    db.refresh(user)
    return master_profile_payload(db, user)


def master_profile_payload(db: Session, user: User) -> dict:
    from backend.app.services.preferences_service import get_profile, _application_row

    profile = user.profile
    prefs = db.scalar(select(ApplicationPreferences).where(ApplicationPreferences.user_id == user.id))
    if profile is not None and profile.master_migrated_at is None:
        migrate_legacy_master(db, user, profile, prefs)
        db.commit()
        db.refresh(user)
        profile = user.profile

    base = get_profile(db, user)
    master = ensure_master_data(profile)
    _seed_common_answers(master)
    completion = compute_completion(user, profile, master)
    photo_url = None
    if profile and profile.photo_storage_key:
        photo_url = f"/api/profile/photo"
    updated = profile.updated_at if profile else None
    return {
        **base,
        "master": master,
        "photo_url": photo_url,
        "updated_at": updated.isoformat() if updated else None,
        "completion": completion,
    }


def compute_completion(user: User, profile: UserProfile | None, master: dict) -> dict:
    scores: dict[str, float] = {}
    missing: list[dict] = []
    section_nav = {
        "personal": "personal",
        "photo": "personal",
        "professional": "professional",
        "education": "education",
        "employment": "employment",
        "skills": "skills",
        "projects": "projects",
        "accomplishments": "accomplishments",
        "career": "career",
        "common_answers": "common",
    }

    personal = master.get("personal") or {}
    professional = master.get("professional") or {}

    def mark(section: str, ok: bool, label: str) -> None:
        weight = _COMPLETION_WEIGHTS.get(section, 0)
        scores[section] = weight if ok else 0
        if not ok and weight:
            meta = _MISSING_META.get(section) or {}
            missing.append(
                {
                    "section": section_nav.get(section, section),
                    "label": label,
                    "hint": str(meta.get("hint") or "Add this section."),
                    "ai": bool(meta.get("ai")),
                }
            )

    mark("personal", bool(user.first_name and user.last_name and (user.email or personal.get("phone") or profile.phone)), "Name and contact")
    mark("photo", bool(profile and profile.photo_storage_key), "Profile photo")
    mark(
        "professional",
        bool(profile and (profile.headline or profile.summary or profile.current_title)),
        "Professional overview",
    )
    edu = (profile.education if profile else []) or []
    mark("education", len(edu) > 0, "Education")
    work = (profile.work_history if profile else []) or []
    named = [
        j
        for j in work
        if isinstance(j, dict) and str(j.get("company") or "").strip()
    ]
    status = str(professional.get("employment_status") or "").strip().lower()
    mark(
        "employment",
        bool(named) or status == "fresher",
        "Employment history",
    )
    skills = master.get("skills") or []
    mark("skills", len(skills) > 0 or bool(profile and profile.skills), "Skills")
    mark("projects", len(master.get("projects") or []) > 0, "Projects")
    mark("accomplishments", True, "Accomplishments")
    career = master.get("career") or {}
    mark(
        "career",
        bool(profile and (profile.preferred_roles or profile.preferred_locations))
        or bool(career.get("desired_industries") or career.get("preferred_roles")),
        "Career preferences",
    )
    common = [a for a in (master.get("common_answers") or []) if isinstance(a, dict) and str(a.get("answer") or "").strip()]
    mark("common_answers", len(common) >= 3, "Common application answers (at least 3)")

    total_weight = sum(_COMPLETION_WEIGHTS.values())
    earned = sum(scores.values())
    percent = int(round(100 * earned / total_weight)) if total_weight else 0
    return {"percent": min(100, max(0, percent)), "missing": missing, "weights": _COMPLETION_WEIGHTS}
