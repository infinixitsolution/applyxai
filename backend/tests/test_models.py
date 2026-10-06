"""Database-level guarantees: uniqueness, partial indexes, cascades, and status vocabularies."""

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, StatementError

from backend.app.models import (
    Application, ApplicationStatus, AutomationJob, AutomationStatus, Job, Resume,
    SearchConfig, UsageCounter, User, UserProfile,
)


def _user(db, email="a@example.com"):
    user = User(email=email, password_hash="argon2-hash-placeholder")
    db.add(user)
    db.commit()
    return user


def _resume(db, user, default=False, path=None):
    resume = Resume(user_id=user.id, name="CV", filename="cv.pdf",
                    storage_path=path or f"resumes/{user.id}/{uuid.uuid4()}.pdf",
                    file_type="pdf", file_size=1000, is_default=default)
    db.add(resume)
    return resume


def test_user_defaults_and_timestamps(db):
    user = _user(db)
    assert user.is_active and not user.is_verified and not user.is_admin
    assert user.created_at is not None and user.updated_at is not None


def test_email_is_unique(db):
    _user(db, "same@example.com")
    db.add(User(email="same@example.com", password_hash="x"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_only_one_default_resume_per_user(db):
    user = _user(db)
    _resume(db, user, default=True)
    _resume(db, user, default=False)
    _resume(db, user, default=False)
    db.commit()
    _resume(db, user, default=True)
    with pytest.raises(IntegrityError):
        db.commit()


def test_default_resume_is_per_user_not_global(db):
    a, b = _user(db, "a@example.com"), _user(db, "b@example.com")
    _resume(db, a, default=True)
    _resume(db, b, default=True)
    db.commit()


def test_only_one_active_automation_per_user(db):
    user = _user(db)
    db.add_all([AutomationJob(user_id=user.id, status=AutomationStatus.COMPLETED),
                AutomationJob(user_id=user.id, status=AutomationStatus.FAILED),
                AutomationJob(user_id=user.id, status=AutomationStatus.RUNNING)])
    db.commit()
    db.add(AutomationJob(user_id=user.id, status=AutomationStatus.QUEUED))
    with pytest.raises(IntegrityError):
        db.commit()


def test_invalid_status_is_rejected(db):
    user = _user(db)
    db.add(AutomationJob(user_id=user.id, status="exploded"))
    with pytest.raises((StatementError, LookupError)):
        db.commit()


def test_status_is_stored_as_lowercase_string(db):
    user = _user(db)
    db.add(AutomationJob(user_id=user.id))
    db.commit()
    assert db.execute(text("SELECT status FROM automation_jobs")).scalar_one() == "queued"


def test_application_unique_per_user_and_job(db):
    a, b = _user(db, "a@example.com"), _user(db, "b@example.com")
    job = Job(external_id="4012345678", title="Python Developer", company="Acme")
    db.add(job)
    db.commit()
    db.add_all([Application(user_id=a.id, job_id=job.id, status=ApplicationStatus.APPLIED),
                Application(user_id=b.id, job_id=job.id, status=ApplicationStatus.SKIPPED)])
    db.commit()
    db.add(Application(user_id=a.id, job_id=job.id))
    with pytest.raises(IntegrityError):
        db.commit()


def test_job_is_unique_per_platform(db):
    db.add_all([Job(external_id="1", title="A"), Job(external_id="1", platform="indeed", title="A")])
    db.commit()
    db.add(Job(external_id="1", title="dup"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_deleting_user_cascades_to_owned_rows_but_keeps_shared_jobs(db):
    user = _user(db)
    job = Job(external_id="99", title="Data Engineer")
    db.add(job)
    db.flush()
    resume = _resume(db, user, default=True)
    db.flush()
    db.add_all([
        UserProfile(user_id=user.id, headline="Engineer"),
        SearchConfig(user_id=user.id, keywords=["Python Developer"], job_type=["Full-time"]),
        Application(user_id=user.id, job_id=job.id, resume_id=resume.id),
        AutomationJob(user_id=user.id),
        UsageCounter(user_id=user.id, period="2026-10", applications=3),
    ])
    db.commit()

    db.execute(text("DELETE FROM users"))
    db.commit()
    for model in (UserProfile, SearchConfig, Resume, Application, AutomationJob, UsageCounter):
        assert db.scalars(select(model)).all() == [], model.__name__
    assert db.scalars(select(Job)).one().external_id == "99"


def test_search_config_keeps_exact_engine_strings(db):
    user = _user(db)
    db.add(SearchConfig(user_id=user.id, experience_level=["Entry level", "Mid-Senior level"],
                        job_type=["Full-time"], on_site=["Remote", "Hybrid"]))
    db.commit()
    db.expire_all()
    cfg = db.scalars(select(SearchConfig)).one()
    assert cfg.experience_level == ["Entry level", "Mid-Senior level"]
    assert cfg.job_type == ["Full-time"]
    assert cfg.on_site == ["Remote", "Hybrid"]
