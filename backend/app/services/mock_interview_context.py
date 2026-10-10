"""Build candidate + job context for mock interviews."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from backend.app.models import Application, Resume, User
from backend.app.services import application_context, preferences_service, resume_service, resume_text_service
from backend.app.services.mock_interview_question_plan import build_question_plan


def build_interview_context(db: Session, user_id: uuid.UUID, application: Application) -> tuple[str, dict]:
    job = application.job
    jd = (job.description or "")[:8000]
    ctx = application_context.build_context(
        db,
        user_id,
        job_description=jd,
        job_title=job.title or "",
        company=job.company or "",
    )
    resume_intake: dict | None = None
    resume_block = ""
    resume_loaded = False
    resume_warning: str | None = None
    profile_skills: list[str] = []

    if application.resume_id:
        resume = db.get(Resume, application.resume_id)
        if resume and resume.user_id == user_id:
            try:
                path = resume_service.absolute_path(resume)
                text = resume_text_service.extract_text(path, resume.file_type)
                if text.strip():
                    resume_intake = resume_text_service.heuristic_profile_intake(text)
                    resume_block = "\n\nResume excerpt:\n" + text.strip()[:6000]
                    resume_loaded = True
                else:
                    resume_warning = "Resume file had no readable text."
            except Exception:
                resume_warning = "Could not read the resume file for this application."
        else:
            resume_warning = "No resume is attached to this application."
    else:
        resume_warning = "No resume is attached to this application."

    user = db.get(User, user_id)
    if user:
        prof = preferences_service.get_profile(db, user)
        profile_skills = [str(s) for s in (prof.get("skills") or []) if s]
        if not resume_intake and (prof.get("work_history") or prof.get("skills")):
            resume_intake = {
                "work_history": prof.get("work_history") or [],
                "skills": profile_skills,
                "summary": prof.get("summary") or "",
                "current_title": prof.get("current_title"),
                "current_company": prof.get("current_company"),
            }

    plan = build_question_plan(
        job_title=job.title or "",
        company=job.company or "",
        job_description=jd,
        resume_intake=resume_intake,
        profile_skills=profile_skills,
    )
    full = f"{ctx}\n\n{plan}{resume_block}"
    snapshot = {
        "job_title": job.title or "",
        "company": job.company or "",
        "application_id": str(application.id),
        "description_excerpt": (job.description or "")[:500],
        "resume_loaded": resume_loaded,
        "resume_warning": resume_warning,
    }
    return full, snapshot
