"""Platform settings API and notification email toggles."""

import pytest
from sqlalchemy import select

from backend.app.core.platform_defaults import DEFAULT_CMS, PLATFORM_SETTINGS_KEY
from backend.app.models import PlatformSettings, User
from backend.app.services import notification_service, platform_settings_service as ps
from backend.app.schemas.platform_settings import AuthEmailIn, CmsIn, NotificationsIn, NotificationTypeIn, SmtpIn
from backend.tests.conftest import csrf_headers


def test_public_site_no_auth(api):
    resp = api.get("/api/site/public")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["branding"]["app_name"] == DEFAULT_CMS["branding"]["app_name"]
    assert "landing" in data
    assert "seo" in data
    assert data["seo"]["site_url"]
    assert "smtp" not in data


def test_robots_and_sitemap(api):
    robots = api.get("/api/site/robots.txt")
    assert robots.status_code == 200
    assert "Sitemap:" in robots.text
    sitemap = api.get("/api/site/sitemap.xml")
    assert sitemap.status_code == 200
    assert "<urlset" in sitemap.text


def test_admin_settings_requires_admin(api, make_user):
    client = make_user("user@example.com")
    assert client.get("/api/admin/settings").status_code == 403


def test_admin_can_update_cms(api, make_user, engine):
    admin = make_user("admin@example.com")
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        user = session.scalar(select(User).where(User.email == "admin@example.com"))
        user.is_admin = True
        session.commit()
    with Session(engine) as session:
        payload = ps.get_effective_cms(session)
    payload["branding"]["app_name"] = "ApplyXAI Test"
    resp = admin.put("/api/admin/settings/cms", json=CmsIn.model_validate(payload).model_dump(), headers=csrf_headers(admin))
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["cms"]["branding"]["app_name"] == "ApplyXAI Test"
    public = api.get("/api/site/public").json()["data"]
    assert public["branding"]["app_name"] == "ApplyXAI Test"


def test_smtp_encrypt_round_trip(db, monkeypatch):
    monkeypatch.setattr("backend.app.core.config.settings.SECRET_KEY", "x" * 32)
    encrypted = ps.encrypt_secret("secret-pass")
    assert ps.decrypt_secret(encrypted) == "secret-pass"
    ps.update_smtp(db, SmtpIn(enabled=True, host="smtp.example.com", port=587, username="u", password="p", from_address="ApplyXAI <a@b.com>"))
    db.commit()
    eff = ps.get_effective_smtp(db)
    assert eff.host == "smtp.example.com"
    assert eff.password == "p"


def test_notification_email_when_enabled(db, outbox, monkeypatch):
    monkeypatch.setattr("backend.app.services.notification_service.get_email_sender", lambda _db: outbox)
    monkeypatch.setattr("backend.app.services.notification_service.smtp_configured", lambda _db: True)
    user = User(email="notify@example.com", password_hash="x", is_verified=True, is_active=True)
    db.add(user)
    db.flush()
    row = db.get(PlatformSettings, PLATFORM_SETTINGS_KEY)
    if row is None:
        row = PlatformSettings(key=PLATFORM_SETTINGS_KEY)
        db.add(row)
        db.flush()
    prefs = ps.get_notification_prefs(db)
    prefs["run_finished"]["email"] = True
    row.notifications = prefs
    db.commit()
    notification_service.notify(db, user.id, "run_finished", "Done", "2 applied", "/automation")
    assert len(outbox.sent) == 1
    assert outbox.sent[0].to == "notify@example.com"
