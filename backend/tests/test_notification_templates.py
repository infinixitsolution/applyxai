"""Notification templates, user email prefs, and admin broadcast."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.models import User, UserProfile
from backend.app.services import notification_service, platform_settings_service as ps, template_service as ts
from backend.app.services import preferences_service
from backend.app.schemas.activity import NotificationPreferencesIn, NotificationPrefTypeIn
from backend.app.schemas.platform_settings import (
    AuthEmailTemplateIn,
    EmailTemplatesIn,
    EventTemplateIn,
    NotificationsIn,
    NotificationTypeIn,
)
from backend.tests.conftest import csrf_headers


@pytest.fixture
def admin(app, db, make_user):
    client = make_user("admin-notify@example.com", client=TestClient(app, raise_server_exceptions=False))
    user = db.scalar(select(User).where(User.email == "admin-notify@example.com"))
    user.is_admin = True
    db.commit()
    return client


def _verified_user(db, email: str) -> User:
    user = User(email=email, password_hash="x", is_verified=True, is_active=True)
    db.add(user)
    db.flush()
    db.add(UserProfile(user_id=user.id))
    db.commit()
    return user


def test_render_replaces_placeholders():
    out = ts.render("Hello {name}, {missing}", {"name": "Ada"})
    assert out == "Hello Ada, "


def test_job_applied_and_daily_report_templates_present(db):
    templates = ps.get_email_templates(db)
    for key in ("job_applied", "daily_report"):
        assert key in templates["events"]
        assert templates["events"][key]["email_subject"]
    prefs = ps.get_notification_prefs(db)
    assert prefs["job_applied"]["label"]
    assert prefs["daily_report"]["label"]


def test_sync_platform_defaults_adds_new_template_keys(db):
    row = ps._row(db)
    stale = {
        "auth": dict(ps.get_email_templates(db)["auth"]),
        "events": {k: v for k, v in ps.get_email_templates(db)["events"].items() if k not in ("job_applied", "daily_report")},
    }
    row.email_templates = stale
    stale_notif = {k: v for k, v in ps.get_notification_prefs(db).items() if k not in ("job_applied", "daily_report")}
    row.notifications = stale_notif
    db.commit()

    assert ps.sync_platform_defaults(db)
    db.commit()
    templates = ps.get_email_templates(db)
    assert "job_applied" in templates["events"]
    assert "daily_report" in templates["events"]
    assert "job_applied" in ps.get_notification_prefs(db)


def test_update_email_templates(db):
    current = ps.get_email_templates(db)
    payload = EmailTemplatesIn(
        auth={k: AuthEmailTemplateIn(**v) for k, v in current["auth"].items()},
        events={k: EventTemplateIn(**v) for k, v in current["events"].items()},
    )
    payload.auth["verify_email"].subject = "Custom verify {app_name}"
    saved = ps.update_email_templates(db, payload)
    db.commit()
    assert saved["auth"]["verify_email"]["subject"] == "Custom verify {app_name}"


def test_user_email_opt_out_blocks_email_only(db, monkeypatch):
    user = _verified_user(db, "optout@example.com")
    ps.update_notifications(db, NotificationsIn(types={"run_finished": NotificationTypeIn(email=True)}))
    db.commit()

    sent = []

    class FakeSender:
        def send(self, email):
            sent.append(email)

    monkeypatch.setattr("backend.app.services.notification_service.smtp_configured", lambda _db: True)
    monkeypatch.setattr("backend.app.services.notification_service.get_email_sender", lambda _db: FakeSender())

    notification_service.notify_event(
        db, user.id, "run_finished", link="/automation", variables={"title": "Done", "message": "ok"},
    )
    assert len(sent) == 1

    prefs = preferences_service.get_notification_preferences(db, user)
    prefs["types"]["run_finished"]["email"] = False
    preferences_service.update_notification_preferences(
        db,
        user,
        NotificationPreferencesIn(types={"run_finished": NotificationPrefTypeIn(email=False)}),
    )

    sent.clear()
    notification_service.notify_event(
        db, user.id, "run_finished", link="/automation", variables={"title": "Again", "message": "ok"},
    )
    assert len(sent) == 0
    assert notification_service.unread_count(db, user.id) >= 2


def test_admin_broadcast(admin, db):
    u1 = _verified_user(db, "b1@example.com")
    u2 = _verified_user(db, "b2@example.com")
    r = admin.post(
        "/api/admin/notifications/broadcast",
        json={"title": "Maintenance", "body": "Tonight", "link": "/app", "user_ids": [str(u1.id), str(u2.id)]},
        headers=csrf_headers(admin),
    )
    assert r.status_code == 200
    assert r.json()["data"]["sent"] == 2
    assert notification_service.unread_count(db, u1.id) == 1
