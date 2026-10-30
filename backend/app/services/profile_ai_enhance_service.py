"""Run Master Profile AI fills from the default resume in one pass."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.models import User
from backend.app.services import (
    career_ai_service,
    common_answers_ai_service,
    employment_ai_service,
    master_profile_service,
    professional_ai_service,
    projects_ai_service,
    resume_ai_service,
    run_config_service,
    screening_ai_service,
    skills_ai_service,
)


def _detail(step_id: str, result: object) -> str:
    if not isinstance(result, dict):
        return ""
    if step_id == "resume":
        return "education, employment, and skills from resume"
    if step_id == "professional":
        filled = result.get("filled") or []
        return ", ".join(str(x) for x in filled) if filled else "already complete"
    if step_id == "employment":
        kind = result.get("kind") or "employment"
        jobs = result.get("jobs") or []
        return result.get("note") or f"{kind}: {len(jobs)} job(s)"
    if step_id == "skills":
        names = result.get("skills") or []
        return f"filled {len(names)} skill{'s' if len(names) != 1 else ''}"
    if step_id == "projects":
        added = result.get("added") or []
        kind = result.get("kind") or "project"
        if added:
            return f"added {len(added)} {kind} project{'s' if len(added) != 1 else ''}"
        return "no new projects"
    if step_id == "career":
        roles = result.get("preferred_roles") or []
        locs = result.get("preferred_locations") or []
        return f"{len(roles)} roles, {len(locs)} locations"
    if step_id == "common_answers":
        filled = result.get("filled") or []
        return f"filled {len(filled)}" if filled else "no empty answers"
    if step_id == "screening":
        filled = result.get("filled") or []
        return f"filled {len(filled)}" if filled else "no empty fields"
    return ""


def enhance_master_profile(db: Session, user: User) -> dict:
    if user.profile is None:
        raise AppError("VALIDATION_ERROR", "Create a profile first.", 422)

    steps: list[dict] = []
    sources: list[str] = []

    def run_step(step_id: str, fn) -> None:
        db.refresh(user)
        try:
            result = fn()
            source = result.get("source") if isinstance(result, dict) else None
            if source:
                sources.append(str(source))
            steps.append(
                {
                    "id": step_id,
                    "ok": True,
                    "source": source,
                    "detail": _detail(step_id, result),
                }
            )
        except AppError as exc:
            steps.append({"id": step_id, "ok": False, "detail": exc.message})

    resume = run_config_service.default_resume(db, user.id)
    if resume is not None:
        run_step(
            "resume",
            lambda: resume_ai_service.intake_from_resume(db, user, resume.id, apply=True),
        )
    else:
        steps.append({"id": "resume", "ok": False, "detail": "No default resume uploaded."})

    run_step("employment", lambda: employment_ai_service.fill_employment_from_resume(db, user))
    run_step("skills", lambda: skills_ai_service.fill_skills_from_resume(db, user))
    run_step("professional", lambda: professional_ai_service.complete_professional_overview(db, user))
    run_step("projects", lambda: projects_ai_service.fill_projects_from_resume(db, user))
    run_step("career", lambda: career_ai_service.enhance_career_preferences(db, user))
    run_step("common_answers", lambda: common_answers_ai_service.fill_common_answers_from_resume(db, user))
    run_step("screening", lambda: screening_ai_service.fill_screening_from_resume(db, user))

    db.refresh(user)
    payload = master_profile_service.master_profile_payload(db, user)
    completion = payload.get("completion") or {}
    return {
        "source": "ai" if "ai" in sources else "heuristic",
        "steps": steps,
        "percent": int(completion.get("percent") or 0),
        "missing": list(completion.get("missing") or []),
        "profile": payload,
    }
