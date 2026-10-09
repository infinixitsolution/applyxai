"""Build text context for application-form AI answers."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from backend.app.models import User
from backend.app.services import preferences_service, run_config_service


def build_context(db: Session, user_id: uuid.UUID, *, job_description: str = "", job_title: str = "", company: str = "") -> str:
    user = db.get(User, user_id)
    if user is None:
        return ""
    values = run_config_service.engine_values(db, user_id)
    doc = preferences_service.application_document(db, user)
    parts = [
        f"Name: {values.get('first_name', '')} {values.get('last_name', '')}".strip(),
        f"Phone: {values.get('phone_number', '')}",
        f"Years of experience (total): {values.get('years_of_experience', '')}",
        f"Visa sponsorship needed: {values.get('require_visa', '')}",
        f"Legally authorized: {values.get('legally_authorized', '')}",
        f"Desired salary: {values.get('desired_salary', '')}",
        f"Notice period (days): {values.get('notice_period', '')}",
        f"LinkedIn: {values.get('linkedIn', '')}",
        f"Headline: {values.get('linkedin_headline', '')}",
        f"Summary: {values.get('linkedin_summary', '')}",
    ]
    if doc.get("user_information_all"):
        parts.append("Additional facts:\n" + doc["user_information_all"])
    else:
        prof = preferences_service.get_profile(db, user)
        block = []
        for job in prof.get("work_history") or []:
            if not isinstance(job, dict):
                continue
            block.append(
                f"Work: {job.get('title', '')} at {job.get('company', '')} "
                f"({job.get('start', '')}-{job.get('end', '')}). {job.get('summary', '')}".strip()
            )
        for ed in prof.get("education") or []:
            if not isinstance(ed, dict):
                continue
            block.append(
                f"Education: {ed.get('degree', '')} {ed.get('field', '')} — {ed.get('school', '')} "
                f"({ed.get('end_year', '')})".strip()
            )
        if prof.get("skills"):
            block.append("Skills: " + ", ".join(prof["skills"][:50]))
        if block:
            parts.append("Additional facts:\n" + "\n".join(block))
    if job_title or company:
        parts.append(f"Job: {job_title} at {company}".strip())
    if job_description:
        parts.append("Job description excerpt:\n" + job_description[:8000])
    return "\n".join(p for p in parts if p and not p.endswith(": "))
