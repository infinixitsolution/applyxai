"""Helpers that create activity the way the automation worker will (through the services)."""

from datetime import datetime, timezone

from backend.app.models import ApplicationStatus, User
from backend.app.services import application_service


def user_id(db, email: str):
    return db.query(User).filter_by(email=email).one().id


def add_application(db, email: str, external_id: str, status=ApplicationStatus.APPLIED, *, title="Python Developer",
                    company="Acme", location="Remote", applied_at: datetime | None = None, **job_fields):
    job = application_service.upsert_job(db, external_id=external_id, title=title, company=company,
                                         location=location, job_url=f"https://www.linkedin.com/jobs/view/{external_id}",
                                         **job_fields)
    app = application_service.record_application(
        db, user_id(db, email), job, status,
        failure_reason="Form had an unanswerable question" if status == ApplicationStatus.FAILED else "",
        applied_at=applied_at or (datetime.now(timezone.utc) if status == ApplicationStatus.APPLIED else None),
    )
    db.commit()
    return app
