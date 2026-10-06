from datetime import datetime, timezone

import pytest

from automation.run_config import build_run_config
from backend.app import cli
from backend.app.core.security import hash_password
from backend.app.models import (
    Application, ApplicationPreferences, ApplicationStatus, AutomationJob, AutomationLog, AutomationStatus, Job,
    Notification, SearchConfig, UsageCounter, User, UserProfile,
)
from backend.app.services import run_config_service
from backend.app.services.ingest_service import ingest_events


@pytest.fixture
def users(db):
    alice = User(email="alice@example.com", password_hash=hash_password("x" * 12), is_verified=True,
                 first_name="Alice", last_name="Rao")
    bob = User(email="bob@example.com", password_hash=hash_password("x" * 12), is_verified=True)
    db.add_all([alice, bob])
    db.commit()
    return alice, bob


@pytest.fixture
def run(db, users):
    job = AutomationJob(user_id=users[0].id, status=AutomationStatus.QUEUED)
    db.add(job)
    db.commit()
    return job


def e(kind, **fields):
    return {"event": kind, "ts": "2026-10-07T04:00:00+00:00", **fields}


def started(job_id, title, company="Acme"):
    return e("job_started", job_id=job_id, title=title, company=company, work_location="Pune", work_style="Hybrid")


def status_of(db, user, external_id):
    return db.query(Application).join(Job).filter(Application.user_id == user.id, Job.external_id == external_id).one().status


def usage(db, user):
    db.expire_all()
    row = db.query(UsageCounter).filter_by(user_id=user.id).one_or_none()
    return (row.applications, row.jobs_discovered) if row else (0, 0)


def test_a_live_run_updates_applications_counters_logs_and_notifies(db, users, run):
    alice, _ = users
    first = [
        e("run_started", search_terms=["Python Developer"]),
        e("login_required"),
        started("101", "Python Developer"),
        e("applied", job_id="101", title="Python Developer", company="Acme", work_location="Pune", work_style="Hybrid",
          description="Build APIs", job_link="https://www.linkedin.com/jobs/view/101",
          date_applied="2026-10-07T09:45:00+05:30"),
        started("102", "Django Developer", "Initech"),
    ]
    result = ingest_events(db, alice.id, first, run=run)
    db.commit()
    assert run.status == AutomationStatus.RUNNING and run.current_job == "Django Developer at Initech"

    second = [
        e("failed", job_id="102", reason="Problem in Easy Applying", detail="Submit button missing"),
        started("103", "Data Engineer"),
        e("skipped", job_id="103", reason="Found Blacklisted words in About Company"),
        e("external", job_id="104", title="Backend Engineer", company="Globex", application_link="https://globex.example/apply"),
        e("paused"), e("resumed"),
        e("run_finished", applied=1, external=1, failed=1, skipped=1, stopped=False, error=""),
    ]
    result = ingest_events(db, alice.id, second, run=run, context=result.context)
    db.commit()

    assert (result.failed, result.skipped, result.external, result.finished) == (1, 1, 1, True)
    assert (run.total_jobs, run.successful_count, run.failed_count, run.skipped_count) == (4, 1, 1, 1)
    assert run.status == AutomationStatus.COMPLETED and run.finished_at is not None and run.current_job == ""

    failed = db.query(Application).join(Job).filter(Job.external_id == "102").one()
    assert failed.job.title == "Django Developer" and failed.job.company == "Initech"   # from job_started
    assert failed.failure_reason == "Problem in Easy Applying: Submit button missing"
    assert failed.automation_job_id == run.id
    applied = db.query(Application).join(Job).filter(Job.external_id == "101").one()
    assert applied.applied_at == datetime(2026, 10, 7, 4, 15, tzinfo=timezone.utc)
    assert status_of(db, alice, "104") == ApplicationStatus.EXTERNAL
    assert usage(db, alice) == (1, 4)

    logs = db.query(AutomationLog).filter_by(automation_job_id=run.id).order_by(AutomationLog.seq).all()
    assert [log.seq for log in logs] == list(range(1, len(first) + len(second) + 1))
    assert logs[1].level == "warning" and "Sign in to LinkedIn" in logs[1].message
    assert "Build APIs" not in " ".join(log.message for log in logs)            # descriptions aren't logged
    note = db.query(Notification).filter_by(user_id=alice.id).one()
    assert note.title == "Automation run finished" and note.link == "/automation"


@pytest.mark.parametrize("final, status", [
    ({"stopped": True, "error": ""}, AutomationStatus.CANCELLED),
    ({"stopped": False, "error": "The browser window was closed."}, AutomationStatus.FAILED),
])
def test_run_end_states(db, users, run, final, status):
    ingest_events(db, users[0].id, [e("run_started"), e("run_finished", **final)], run=run)
    db.commit()
    assert run.status == status
    assert run.error_message == final["error"]


def test_a_run_cannot_be_fed_events_for_another_user(db, users, run):
    with pytest.raises(ValueError):
        ingest_events(db, users[1].id, [e("run_started")], run=run)


def test_invalid_events_are_ignored(db, users, run):
    result = ingest_events(db, users[0].id, [{"event": "applied"}, {"event": "rm -rf"}, "junk", None], run=run)
    db.commit()
    assert result.applied == 0 and db.query(AutomationLog).count() == 0 and db.query(Job).count() == 0


def test_imported_history_is_idempotent_and_does_not_use_the_plan_limit(db, users):
    alice, bob = users
    history = [
        e("failed", job_id="201", reason="Problem in Easy Applying"),
        e("applied", job_id="201", title="Python Developer", company="Acme", date_applied="2026-01-05 10:00:00"),
        e("applied", job_id="202", title="API Developer", company="Stark"),
    ]
    for _ in range(2):
        ingest_events(db, alice.id, history, count_usage=False)
        db.commit()
    assert db.query(Application).filter_by(user_id=alice.id).count() == 2
    assert status_of(db, alice, "201") == ApplicationStatus.APPLIED            # later success wins
    assert usage(db, alice) == (0, 0)
    assert db.query(Application).filter_by(user_id=bob.id).count() == 0


def test_engine_values_build_a_valid_run_config(db, users, tmp_path):
    alice, _ = users
    assert run_config_service.readiness_problems(db, alice.id)               # nothing saved yet
    db.add_all([
        UserProfile(user_id=alice.id, phone="+91 98765 43210", experience_years=4, current_company="Acme",
                    headline="Backend engineer"),
        SearchConfig(user_id=alice.id, keywords=["Python Developer"], location="Pune", experience_level=["Entry level"],
                     job_type=["Full-time"], on_site=["Remote"], extra={"bad_words": ["unpaid"]}),
        ApplicationPreferences(user_id=alice.id, answers={"years_of_experience": "5", "require_visa": "No"}),
    ])
    db.commit()

    values = run_config_service.engine_values(db, alice.id)
    assert run_config_service.readiness_problems(db, alice.id) == []
    assert values["years_of_experience"] == "5"                              # explicit answer beats the profile
    assert values["recent_employer"] == "Acme" and values["search_terms"] == ["Python Developer"]
    config = build_run_config(values, history_dir=tmp_path / "h", run_dir=tmp_path / "r")
    assert config["search"]["bad_words"] == ["unpaid"] and config["personals"]["phone_number"] == "+91 98765 43210"


def test_cli_imports_engine_csvs_into_an_account(db, engine, users, tmp_path, monkeypatch, capsys):
    from sqlalchemy.orm import sessionmaker
    applied = tmp_path / "applied.csv"
    applied.write_text(
        "Job ID,Title,Company,Work Location,Work Style,About Job,Date Applied,Job Link,External Job link\n"
        "301,Python Developer,Acme,Pune,Remote,Build things,2026-02-01 09:00:00,https://www.linkedin.com/jobs/view/301,Easy Applied\n",
        encoding="utf-8")
    failed = tmp_path / "failed.csv"
    failed.write_text("Job ID,Job Link,Date Tried,Assumed Reason,External Job link\n"
                      "302,https://www.linkedin.com/jobs/view/302,2026-02-01 10:00:00,Found Blacklisted words,Skipped\n",
                      encoding="utf-8")
    monkeypatch.setattr(cli, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))

    assert cli.main(["import-history", "--email", "ALICE@example.com", "--applied", str(applied), "--failed", str(failed)]) == 0
    assert "Imported 1 applied, 0 external, 0 failed, 1 skipped" in capsys.readouterr().out
    assert status_of(db, users[0], "301") == ApplicationStatus.APPLIED
    assert status_of(db, users[0], "302") == ApplicationStatus.SKIPPED

    assert cli.main(["import-history", "--email", "nobody@example.com", "--applied", str(applied)]) == 1
    assert cli.main(["import-history", "--email", "alice@example.com", "--applied", str(tmp_path / "x.csv"),
                     "--failed", str(tmp_path / "y.csv")]) == 1
