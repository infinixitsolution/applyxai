from datetime import datetime, timezone

import pytest

from backend.app.core.security import hash_password
from backend.app.models import ApplicationStatus, AutomationJob, Job, Resume, UsageCounter, User
from backend.app.services import application_service, notification_service, usage_service


@pytest.fixture
def users(db):
    alice = User(email="alice@example.com", password_hash=hash_password("x" * 12), is_verified=True)
    bob = User(email="bob@example.com", password_hash=hash_password("x" * 12), is_verified=True)
    db.add_all([alice, bob])
    db.commit()
    return alice, bob


def counter(db, user):
    db.expire_all()
    return db.query(UsageCounter).filter_by(user_id=user.id).one_or_none()


def test_upsert_job_is_idempotent_and_never_blanks_details(db):
    job = application_service.upsert_job(db, external_id="123", title="Dev", company="Acme", location="Pune")
    db.commit()
    again = application_service.upsert_job(db, external_id="123", title="Senior Dev", company="", location=None)
    db.commit()
    assert again.id == job.id and db.query(Job).count() == 1
    assert (again.title, again.company, again.location) == ("Senior Dev", "Acme", "Pune")


def test_upsert_job_rejects_bad_input(db):
    with pytest.raises(ValueError):
        application_service.upsert_job(db, external_id="", title="Dev")
    with pytest.raises(ValueError):
        application_service.upsert_job(db, external_id="1", title="Dev", user_id="sneaky")


def test_record_application_counts_usage_exactly_once(db, users):
    alice, _ = users
    job = application_service.upsert_job(db, external_id="1", title="Dev")
    app = application_service.record_application(db, alice.id, job, ApplicationStatus.QUEUED)
    db.commit()
    assert (counter(db, alice).jobs_discovered, counter(db, alice).applications) == (1, 0)

    application_service.record_application(db, alice.id, job, ApplicationStatus.APPLIED)
    db.commit()
    assert (counter(db, alice).jobs_discovered, counter(db, alice).applications) == (1, 1)
    assert app.applied_at is not None

    # Seeing an applied job again (re-run, "already applied") changes nothing.
    application_service.record_application(db, alice.id, job, ApplicationStatus.SKIPPED)
    application_service.record_application(db, alice.id, job, ApplicationStatus.APPLIED)
    db.commit()
    assert counter(db, alice).applications == 1 and app.status == ApplicationStatus.APPLIED


def test_failure_reason_only_kept_for_failures(db, users):
    alice, _ = users
    job = application_service.upsert_job(db, external_id="1", title="Dev")
    app = application_service.record_application(db, alice.id, job, ApplicationStatus.FAILED, failure_reason="boom")
    assert app.failure_reason == "boom"
    application_service.record_application(db, alice.id, job, ApplicationStatus.SKIPPED, failure_reason="ignored")
    assert app.failure_reason == ""


def test_shared_job_gives_each_user_their_own_application(db, users):
    alice, bob = users
    job = application_service.upsert_job(db, external_id="1", title="Dev")
    a = application_service.record_application(db, alice.id, job, ApplicationStatus.APPLIED)
    b = application_service.record_application(db, bob.id, job, ApplicationStatus.FAILED)
    db.commit()
    assert a.id != b.id and a.job_id == b.job_id
    assert counter(db, alice).applications == 1 and counter(db, bob).applications == 0


def test_record_application_rejects_other_users_resume_or_run(db, users):
    alice, bob = users
    resume = Resume(user_id=bob.id, name="b", filename="b.pdf", storage_path="resumes/b.pdf", file_type="pdf",
                    file_size=1)
    run = AutomationJob(user_id=bob.id)
    db.add_all([resume, run])
    db.commit()
    job = application_service.upsert_job(db, external_id="1", title="Dev")
    with pytest.raises(ValueError):
        application_service.record_application(db, alice.id, job, ApplicationStatus.APPLIED, resume_id=resume.id)
    with pytest.raises(ValueError):
        application_service.record_application(db, alice.id, job, ApplicationStatus.APPLIED,
                                               automation_job_id=run.id)


def test_usage_increment_creates_then_adds(db, users):
    alice, _ = users
    usage_service.increment(db, alice.id, applications=2, runtime_seconds=30)
    usage_service.increment(db, alice.id, applications=1, jobs_discovered=5)
    usage_service.increment(db, alice.id)                       # no-op
    db.commit()
    c = counter(db, alice)
    assert (c.applications, c.jobs_discovered, c.runtime_seconds) == (3, 5, 30)
    with pytest.raises(ValueError):
        usage_service.increment(db, alice.id, resumes=1)


def test_usage_is_per_calendar_month(db, users):
    alice, _ = users
    usage_service.increment(db, alice.id, applications=4, now=datetime(2026, 9, 30, 23, 59, tzinfo=timezone.utc))
    usage_service.increment(db, alice.id, applications=1, now=datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc))
    db.commit()
    periods = {c.period: c.applications for c in db.query(UsageCounter).filter_by(user_id=alice.id)}
    assert periods == {"2026-09": 4, "2026-10": 1}


@pytest.mark.parametrize("period,start,end", [
    ("2026-10", datetime(2026, 10, 1, tzinfo=timezone.utc), datetime(2026, 11, 1, tzinfo=timezone.utc)),
    ("2026-12", datetime(2026, 12, 1, tzinfo=timezone.utc), datetime(2027, 1, 1, tzinfo=timezone.utc)),
])
def test_period_bounds(period, start, end):
    assert usage_service.period_bounds(period) == (start, end)


def test_usage_summary_and_limit(db, users):
    alice, _ = users
    usage_service.increment(db, alice.id, applications=10)
    db.commit()
    summary = usage_service.usage_summary(db, alice.id)
    assert summary["plan"] == "free"
    assert summary["applications"] == {"used": 10, "limit": 10, "remaining": 0}
    assert summary["limit_reached"] is True
    assert usage_service.remaining_applications(db, alice.id) == 0


@pytest.mark.parametrize("link", ["https://evil.example", "//evil.example", "javascript:alert(1)", "/\\evil"])
def test_notification_links_must_be_in_app(db, users, link):
    with pytest.raises(ValueError):
        notification_service.notify(db, users[0].id, "run_finished", "Done", link=link)


def test_notify_and_read(db, users):
    alice, bob = users
    note = notification_service.notify(db, alice.id, "run_finished", "Run finished", "3 applied", "/automation")
    db.commit()
    assert notification_service.unread_count(db, alice.id) == 1
    with pytest.raises(Exception):
        notification_service.mark_read(db, bob.id, note.id)          # not bob's
    notification_service.mark_read(db, alice.id, note.id)
    assert notification_service.unread_count(db, alice.id) == 0
