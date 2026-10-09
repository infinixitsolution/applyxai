"""
Celery worker and beat schedule. Runs go to the user's desktop agent, so the workers only do
scheduled housekeeping. From the project root (Windows needs the solo pool):

    celery -A backend.app.worker worker --beat --pool=solo --loglevel=info

Without Redis/Celery in development, the Automation page still reaps a user's stale runs
whenever it loads; only the cross-user sweep needs beat.
"""

import logging

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
