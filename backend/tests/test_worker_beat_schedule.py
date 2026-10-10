"""Celery beat schedule includes housekeeping tasks."""

from backend.app.worker import celery_app


def test_beat_schedule_includes_mock_interview_abandon():
    tasks = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}
    assert "applyxai.abandon_stale_mock_interviews" in tasks


def test_abandon_stale_mock_interviews_runs_hourly():
    entry = celery_app.conf.beat_schedule["abandon-stale-mock-interviews"]
    assert entry["task"] == "applyxai.abandon_stale_mock_interviews"
    assert entry["schedule"] == 3600.0
