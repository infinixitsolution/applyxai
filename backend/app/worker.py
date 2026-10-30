"""
Celery worker and beat schedule. Runs go to the user's desktop agent, so the workers only do
scheduled housekeeping. From the project root (Windows needs the solo pool):

    celery -A backend.app.worker worker --beat --pool=solo --loglevel=info

Without Redis/Celery in development, the Automation page still reaps a user's stale runs
whenever it loads; only the cross-user sweep needs beat.
"""

import logging
import uuid

from celery import Celery

from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.services import agent_service, automation_service, daily_report_service

logger = logging.getLogger("applyxai.worker")

celery_app = Celery("applyxai", broker=settings.REDIS_URL)
celery_app.conf.update(
    task_ignore_result=True,
    timezone="UTC",
    beat_schedule={
        "reap-stale-runs": {"task": "applyxai.reap_stale_runs", "schedule": 60.0},
        "delete-expired-pairings": {"task": "applyxai.delete_expired_pairings", "schedule": 3600.0},
        "candidate-daily-reports": {
            "task": "applyxai.send_candidate_daily_reports",
            "schedule": 86400.0,
        },
        "abandon-stale-mock-interviews": {
            "task": "applyxai.abandon_stale_mock_interviews",
            "schedule": 3600.0,
        },
        "close-stale-live-interviews": {
            "task": "applyxai.close_stale_live_interviews",
            "schedule": 900.0,
        },
        "outreach-automation-tick": {
            "task": "applyxai.outreach_automation_tick",
            "schedule": 60.0,
        },
    },
)


@celery_app.task(name="applyxai.reap_stale_runs")
def reap_stale_runs() -> int:
    with SessionLocal() as db:
        count = automation_service.reap_stale_runs(db)
        db.commit()
    if count:
        logger.info("reaped %d stale automation runs", count)
    return count


@celery_app.task(name="applyxai.delete_expired_pairings")
def delete_expired_pairings() -> int:
    with SessionLocal() as db:
        count = agent_service.delete_expired_pairings(db)
        db.commit()
    return count


@celery_app.task(name="applyxai.send_candidate_daily_reports")
def send_candidate_daily_reports() -> int:
    with SessionLocal() as db:
        count = daily_report_service.send_daily_reports(db)
        db.commit()
    if count:
        logger.info("sent %d candidate daily report(s)", count)
    return count


@celery_app.task(name="applyxai.abandon_stale_mock_interviews")
def abandon_stale_mock_interviews() -> int:
    from backend.app.services import mock_interview_service

    with SessionLocal() as db:
        count = mock_interview_service.mark_stale_sessions_abandoned(db)
        db.commit()
    logger.info("abandon_stale_mock_interviews complete abandoned=%d", count)
    return count


@celery_app.task(name="applyxai.close_stale_live_interviews")
def close_stale_live_interviews() -> int:
    from backend.app.services import live_interview_service

    with SessionLocal() as db:
        count = live_interview_service.close_stale_active_sessions(db)
        db.commit()
    if count:
        logger.info("close_stale_live_interviews complete closed=%d", count)
    return count


@celery_app.task(name="applyxai.mock_interview_feedback", bind=True, max_retries=2)
def run_mock_interview_feedback_job(self, job_id: str) -> str:
    from backend.app.services.mock_interview_feedback_jobs import run_feedback_job

    with SessionLocal() as db:
        run_feedback_job(db, __import__("uuid").UUID(job_id))
        db.commit()
    return job_id


@celery_app.task(name="applyxai.run_institute_scrape_job")
def run_institute_scrape_job(job_id: str) -> str:
    from backend.app.services import institute_scrape_service

    with SessionLocal() as db:
        institute_scrape_service.run_scrape_job(db, uuid.UUID(job_id))
        db.commit()
    return job_id


@celery_app.task(name="applyxai.outreach_automation_tick")
def outreach_automation_tick() -> str:
    from backend.app.services import institute_outreach_automation_service

    with SessionLocal() as db:
        result = institute_outreach_automation_service.run_automation_tick(db)
        db.commit()
    return result


@celery_app.task(name="applyxai.run_company_directory_enrichment")
def run_company_directory_enrichment(company_key: str) -> str:
    from backend.app.services import company_directory_service

    with SessionLocal() as db:
        company_directory_service.enrich_profile(db, company_key)
        db.commit()
    return company_key


@celery_app.task(name="applyxai.run_bulk_lead_import_enrichment")
def run_bulk_lead_import_enrichment(lead_ids: list[str]) -> str:
    from backend.app.services import institute_outreach_service

    done = failed = 0
    for lid in lead_ids:
        try:
            institute_outreach_service.run_background_complete_lead_profile(uuid.UUID(lid))
            done += 1
        except Exception:
            failed += 1
    return f"done={done} failed={failed}"


@celery_app.task(name="applyxai.send_institute_outreach")
def send_institute_outreach(lead_id: str, channels: list[str]) -> str:
    from backend.app.services import institute_outreach_service
    from backend.app.services.email_service import get_email_sender

    with SessionLocal() as db:
        mailer = get_email_sender(db)
        lead = institute_outreach_service.get_lead(db, uuid.UUID(lead_id))
        institute_outreach_service.send_outreach(db, lead, channels, mailer=mailer)
        db.commit()
    return lead_id
