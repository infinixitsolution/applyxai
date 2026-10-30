"""LinkedIn profile sync: readiness, snapshot, sync plan, and run options."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models import User
from backend.app.services import agent_service, master_profile_service

RUN_KIND_JOB_APPLY = "job_apply"
RUN_KIND_PROFILE_SYNC = "linkedin_profile_sync"

SYNC_SECTIONS = (
    "photo",
    "headline",
    "about",
    "experience",
    "education",
    "skills",
    "location",
    "industry",
)

DEFAULT_SECTIONS = list(SYNC_SECTIONS)


def _profile(user: User):
    return user.profile


def _master(user: User) -> dict:
    profile = _profile(user)
    return master_profile_service.ensure_master_data(profile)


def _dedupe_skills(master: dict, profile) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in list(master.get("skills") or []) + list((profile.skills if profile else []) or []):
        if isinstance(raw, dict):
            name = str(raw.get("name") or raw.get("skill") or "").strip()
        else:
            name = str(raw).strip()
        key = name.lower()
        if name and key not in seen:
            seen.add(key)
            out.append(name)
    return out


def _location_string(master: dict) -> str:
    personal = master.get("personal") or {}
    parts = [
        str(personal.get("city") or "").strip(),
        str(personal.get("state") or "").strip(),
        str(personal.get("country") or "").strip(),
    ]
    return ", ".join(p for p in parts if p)


def build_snapshot(db: Session, user: User) -> dict:
    """Normalized payload for the browser engine."""
    profile = _profile(user)
    master = _master(user)
    career = master.get("career") or {}
    work = list((profile.work_history if profile else []) or [])
    edu = list((profile.education if profile else []) or [])
    return {
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "phone": (profile.phone if profile else "") or "",
        "headline": (profile.headline if profile else "") or "",
        "about": (profile.summary if profile else "") or "",
        "experience": work,
        "education": edu,
        "skills": _dedupe_skills(master, profile),
        "location": _location_string(master),
        "industry": (career.get("desired_industries") or [None])[0] if isinstance(career.get("desired_industries"), list) else "",
        "linkedin_url": str(career.get("linkedin_url") or "").strip(),
        "has_photo": bool(profile and profile.photo_storage_key),
    }


def readiness_problems(db: Session, user: User) -> list[str]:
    if not agent_service.list_devices(db, user.id):
        return ["Connect the ApplyXAI desktop agent on your computer first."]
    profile = _profile(user)
    master = _master(user)
    problems: list[str] = []
    if not (user.first_name and user.last_name):
        problems.append("Add your first and last name to your profile.")
    phone = (profile.phone if profile else "") or ""
    if len(phone.strip()) < 10:
        problems.append("Add a phone number with at least 10 characters.")
    headline = (profile.headline if profile else "") or ""
    if not headline.strip() and not (profile and profile.current_title):
        problems.append("Add a headline or current job title.")
    work = (profile.work_history if profile else []) or []
    edu = (profile.education if profile else []) or []
    if not work and not edu:
        problems.append("Add at least one employment or education entry.")
    skills = _dedupe_skills(master, profile)
    if len(skills) < 3:
        problems.append("Add at least three skills.")
    career = master.get("career") or {}
    if not str(career.get("linkedin_url") or "").strip():
        problems.append("Add your LinkedIn profile URL under Career preferences.")
    return problems


def _section_preview(section: str, snapshot: dict) -> str:
    if section == "photo":
        return "Photo on file" if snapshot.get("has_photo") else ""
    if section == "headline":
        return str(snapshot.get("headline") or "")[:120]
    if section == "about":
        return str(snapshot.get("about") or "")[:200]
    if section == "experience":
        items = snapshot.get("experience") or []
        return f"{len(items)} role(s)" if items else ""
    if section == "education":
        items = snapshot.get("education") or []
        return f"{len(items)} school(s)" if items else ""
    if section == "skills":
        skills = snapshot.get("skills") or []
        return ", ".join(skills[:8]) + ("…" if len(skills) > 8 else "")
    if section == "location":
        return str(snapshot.get("location") or "")
    if section == "industry":
        return str(snapshot.get("industry") or "")
    return ""


def build_sync_plan(
    snapshot: dict,
    *,
    sections: list[str] | None = None,
    overwrite_sections: list[str] | None = None,
    include_photo: bool = True,
) -> list[dict]:
    chosen = [s for s in (sections or DEFAULT_SECTIONS) if s in SYNC_SECTIONS]
    if not include_photo and "photo" in chosen:
        chosen = [s for s in chosen if s != "photo"]
    overwrite = set(overwrite_sections or [])
    plan: list[dict] = []
    for section in chosen:
        preview = _section_preview(section, snapshot)
        has_data = bool(preview) or (section == "photo" and snapshot.get("has_photo"))
        if not has_data and section not in ("location", "industry"):
            plan.append({"section": section, "action": "skip", "reason": "no_master_data", "preview": ""})
            continue
        policy = "overwrite" if section in overwrite else "fill_empty"
        plan.append({
            "section": section,
            "action": "fill",
            "policy": policy,
            "preview": preview,
        })
    plan.append({
        "section": "manual_checklist",
        "action": "manual",
        "preview": "Connections, endorsements, verifications",
    })
    return plan


def normalize_start_options(body: dict | None) -> dict:
    raw = body or {}
    sections = raw.get("sections")
    if sections is not None:
        sections = [str(s) for s in sections if str(s) in SYNC_SECTIONS]
    if not sections:
        sections = list(DEFAULT_SECTIONS)
    overwrite = [str(s) for s in (raw.get("overwrite_sections") or []) if str(s) in SYNC_SECTIONS]
    return {
        "sections": sections,
        "overwrite_sections": overwrite,
        "include_photo": bool(raw.get("include_photo", True)),
        "dry_run": bool(raw.get("dry_run", False)),
        "fill_empty_only": True,
    }


def profile_sync_payload(db: Session, user: User, run_options: dict) -> dict:
    snapshot = build_snapshot(db, user)
    plan = build_sync_plan(
        snapshot,
        sections=run_options.get("sections"),
        overwrite_sections=run_options.get("overwrite_sections"),
        include_photo=run_options.get("include_photo", True),
    )
    return {
        "snapshot": snapshot,
        "plan": plan,
        "settings": {
            "fill_empty_only": run_options.get("fill_empty_only", True),
            "overwrite_sections": list(run_options.get("overwrite_sections") or []),
            "dry_run": bool(run_options.get("dry_run")),
            "include_photo": bool(run_options.get("include_photo", True)),
        },
        "photo_download_path": "/api/agent/runs/{run_id}/profile-photo",
    }
