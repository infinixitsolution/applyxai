"""
Jobs and applications.

User-facing reads always filter on applications.user_id; jobs are reached only through the
caller's own applications (the jobs table is a shared catalogue). The record_* functions are
called server-side by the automation worker (Phase 8), never with client-supplied user IDs.
"""

import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import Select, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, contains_eager

from backend.app.core.errors import AppError
from backend.app.models import Application, ApplicationStatus, AutomationJob, Job, Resume
from backend.app.services import usage_service

SORTS = {
    "created_at": Application.created_at,
    "applied_at": Application.applied_at,
    "updated_at": Application.updated_at,
    "company": Job.company,
    "title": Job.title,
}
DEFAULT_SORT = "-created_at"

_JOB_FIELDS = ("title", "company", "location", "job_url", "description", "salary_min", "salary_max",
               "employment_type", "work_setting", "experience_level")


def _not_found(what: str) -> AppError:
    return AppError("NOT_FOUND", f"{what} not found", status_code=404)


def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _day_start(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


# --- reads (always scoped to one user) ------------------------------------------------

def applications_query(user_id: uuid.UUID, *, status: list[ApplicationStatus] | None = None, q: str | None = None,
                       company: str | None = None, applied_from: date | None = None,
                       applied_to: date | None = None, automation_job_id: uuid.UUID | None = None,
                       sort: str = DEFAULT_SORT) -> Select:
    stmt = (select(Application).join(Application.job).options(contains_eager(Application.job))
            .where(Application.user_id == user_id))
    if status:
        stmt = stmt.where(Application.status.in_(status))
    if q:
        pattern = _like(q.strip())
        stmt = stmt.where(or_(Job.title.ilike(pattern, escape="\\"), Job.company.ilike(pattern, escape="\\"),
                              Job.location.ilike(pattern, escape="\\")))
    if company:
        stmt = stmt.where(Job.company.ilike(_like(company.strip()), escape="\\"))
    if applied_from:
        stmt = stmt.where(Application.applied_at >= _day_start(applied_from))
    if applied_to:
        stmt = stmt.where(Application.applied_at < _day_start(applied_to + timedelta(days=1)))
    if automation_job_id:
        stmt = stmt.where(Application.automation_job_id == automation_job_id)

    descending = sort.startswith("-")
    column = SORTS.get(sort.lstrip("-"))
    if column is None:
        raise AppError("VALIDATION_ERROR", f"sort must be one of: {', '.join(sorted(SORTS))} (prefix - for descending)",
                       status_code=422)
    order = column.desc() if descending else column.asc()
    if column is Application.applied_at:
        order = order.nulls_last()
    return stmt.order_by(order, Application.id)


def get_application(db: Session, user_id: uuid.UUID, application_id: uuid.UUID) -> Application:
    app = db.scalar(select(Application).join(Application.job).options(contains_eager(Application.job))
                    .where(Application.id == application_id, Application.user_id == user_id))
    if app is None:
        raise _not_found("Application")
    return app


def jobs_query(user_id: uuid.UUID, *, q: str | None = None, company: str | None = None,
               work_setting: str | None = None) -> Select:
    stmt = (select(Application).join(Application.job).options(contains_eager(Application.job))
            .where(Application.user_id == user_id))
    if q:
        pattern = _like(q.strip())
        stmt = stmt.where(or_(Job.title.ilike(pattern, escape="\\"), Job.company.ilike(pattern, escape="\\"),
                              Job.description.ilike(pattern, escape="\\")))
    if company:
        stmt = stmt.where(Job.company.ilike(_like(company.strip()), escape="\\"))
    if work_setting:
        stmt = stmt.where(Job.work_setting == work_setting)
    return stmt.order_by(Job.discovered_at.desc(), Job.id)


def get_job(db: Session, user_id: uuid.UUID, job_id: uuid.UUID) -> Application:
    """The caller's application for this job; 404 if they never encountered it."""
    app = db.scalar(select(Application).join(Application.job).options(contains_eager(Application.job))
                    .where(Application.job_id == job_id, Application.user_id == user_id))
    if app is None:
        raise _not_found("Job")
    return app


# --- writes (server-side only) --------------------------------------------------------

def upsert_job(db: Session, *, external_id: str, platform: str = "linkedin", **fields) -> Job:
    unknown = set(fields) - set(_JOB_FIELDS)
    if unknown:
        raise ValueError(f"unknown job fields: {unknown}")
    if not external_id or not fields.get("title"):
        raise ValueError("external_id and title are required")
    where = (Job.platform == platform, Job.external_id == str(external_id))
    for _ in range(2):
        job = db.scalar(select(Job).where(*where))
        if job is not None:
            for name, value in fields.items():
                if value not in (None, ""):          # never erase known details with blanks
                    setattr(job, name, value)
            return job
        try:
            with db.begin_nested():
                job = Job(platform=platform, external_id=str(external_id), **fields)
                db.add(job)
            return job
        except IntegrityError:
            continue                                 # created concurrently; update that row
    raise RuntimeError("could not upsert job")


def resolve_applied_resume_id(
    db: Session,
    user_id: uuid.UUID,
    job: Job,
    *,
    event_resume_id: uuid.UUID | None,
    external_job_id: str,
) -> uuid.UUID | None:
    """
    Pick the resume row that was actually used for an application.
    The agent may omit resume_id when tailoring succeeded server-side before the applied event.
    """
    if event_resume_id:
        return event_resume_id
    app = db.scalar(select(Application).where(Application.user_id == user_id, Application.job_id == job.id))
    if app is not None and app.resume_id:
        resume = db.get(Resume, app.resume_id)
        if resume is not None and resume.user_id == user_id:
            meta = resume.ai_metadata or {}
            if meta.get("generated_by") == "ai" or resume.application_id == app.id:
                return app.resume_id
    key = str(external_job_id or "").strip()
    if not key:
        return None
    rows = db.scalars(
        select(Resume)
        .where(Resume.user_id == user_id)
        .order_by(Resume.created_at.desc())
    ).all()
    for resume in rows:
        meta = resume.ai_metadata or {}
        if meta.get("generated_by") == "ai" and str(meta.get("job_id") or "") == key:
            return resume.id
    return None


def record_application(db: Session, user_id: uuid.UUID, job: Job, status: ApplicationStatus, *,
                       automation_job_id: uuid.UUID | None = None, resume_id: uuid.UUID | None = None,
                       failure_reason: str = "", applied_at: datetime | None = None,
                       count_usage: bool = True) -> Application:
    """
    Create or update the user's application for a job. The first transition to APPLIED counts
    against the monthly limit; a new application row counts as a discovered job. Imported
    history passes count_usage=False. The caller commits.
    """
    if resume_id and db.scalar(select(Resume.id).where(Resume.id == resume_id, Resume.user_id == user_id)) is None:
        raise ValueError("resume does not belong to this user")
    if automation_job_id and db.scalar(select(AutomationJob.id).where(
            AutomationJob.id == automation_job_id, AutomationJob.user_id == user_id)) is None:
        raise ValueError("automation run does not belong to this user")

    db.flush()
    app = db.scalar(select(Application).where(Application.user_id == user_id, Application.job_id == job.id))
    if app is None:
        app = Application(user_id=user_id, job_id=job.id, status=status)
        db.add(app)
        if count_usage:
            usage_service.increment(db, user_id, jobs_discovered=1)
        newly_applied = status == ApplicationStatus.APPLIED
    elif app.status == ApplicationStatus.APPLIED:
        if resume_id:
            app.resume_id = resume_id
        if automation_job_id:
            app.automation_job_id = automation_job_id
        return app
    else:
        newly_applied = status == ApplicationStatus.APPLIED
        app.status = status

    if automation_job_id:
        app.automation_job_id = automation_job_id
    if resume_id:
        app.resume_id = resume_id
    app.failure_reason = failure_reason[:5000] if status == ApplicationStatus.FAILED else ""
    if newly_applied:
        app.applied_at = applied_at or datetime.now(timezone.utc)
        if count_usage:
            usage_service.increment(db, user_id, applications=1)
    db.flush()
    return app


def application_for_external_job(db: Session, user_id: uuid.UUID, external_job_id: str) -> Application | None:
    job_key = str(external_job_id or "").strip()
    if not job_key:
        return None
    job = db.scalar(select(Job).where(Job.external_id == job_key))
    if job is None:
        return None
    return db.scalar(select(Application).where(Application.user_id == user_id, Application.job_id == job.id))


def attach_generated_resume(db: Session, user_id: uuid.UUID, application_id: uuid.UUID, resume_id: uuid.UUID) -> Application:
    app = get_application(db, user_id, application_id)
    resume = db.scalar(select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id))
    if resume is None:
        raise _not_found("Resume")
    resume.application_id = application_id
    app.resume_id = resume_id
    meta = dict(resume.ai_metadata or {})
    meta["application_id"] = str(application_id)
    resume.ai_metadata = meta
    db.flush()
    return app


def generated_resumes_for_applications(db: Session, user_id: uuid.UUID, application_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[Resume]]:
    if not application_ids:
        return {}
    rows = db.scalars(
        select(Resume)
        .where(Resume.user_id == user_id, Resume.application_id.in_(application_ids))
        .order_by(Resume.created_at.desc())
    ).all()
    grouped: dict[uuid.UUID, list[Resume]] = {}
    for row in rows:
        if row.application_id is None:
            continue
        grouped.setdefault(row.application_id, []).append(row)
    return grouped


def primary_resumes(db: Session, user_id: uuid.UUID, resume_ids: list[uuid.UUID]) -> dict[uuid.UUID, Resume]:
    if not resume_ids:
        return {}
    rows = db.scalars(select(Resume).where(Resume.user_id == user_id, Resume.id.in_(resume_ids))).all()
    return {row.id: row for row in rows}
