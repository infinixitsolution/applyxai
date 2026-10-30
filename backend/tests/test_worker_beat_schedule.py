"""Celery beat schedule includes housekeeping tasks."""

from backend.app.worker import celery_app


def test_beat_schedule_includes_mock_interview_abandon():
    tasks = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}
    assert "applyxai.abandon_stale_mock_interviews" in tasks


def test_abandon_stale_mock_interviews_runs_hourly():
    entry = celery_app.conf.beat_schedule["abandon-stale-mock-interviews"]
    assert entry["task"] == "applyxai.abandon_stale_mock_interviews"
    assert entry["schedule"] == 3600.0


def test_beat_schedule_includes_close_stale_live_interviews():
    tasks = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}
    assert "applyxai.close_stale_live_interviews" in tasks


def test_close_stale_live_interviews_runs_every_fifteen_minutes():
    entry = celery_app.conf.beat_schedule["close-stale-live-interviews"]
    assert entry["task"] == "applyxai.close_stale_live_interviews"
    assert entry["schedule"] == 900.0


def test_beat_schedule_includes_outreach_automation():
    tasks = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}
    assert "applyxai.outreach_automation_tick" in tasks
