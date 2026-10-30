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
    assert "Sitemap: https://applyxai.com/sitemap.xml" in robots.text
    sitemap = api.get("/api/site/sitemap.xml")
    assert sitemap.status_code == 200
    assert "<urlset" in sitemap.text
    public_robots = api.get("/robots.txt")
    assert public_robots.status_code == 200 and public_robots.text == robots.text
    public_sitemap = api.get("/sitemap.xml")
    assert public_sitemap.status_code == 200 and public_sitemap.text == sitemap.text


def test_admin_settings_requires_admin(api, make_user):
    client = make_user("user@example.com")
    assert client.get("/api/admin/settings").status_code == 403


def test_admin_activates_job_sources(api, make_user, engine):
    admin = make_user("sources-admin@example.com")
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        user = session.scalar(select(User).where(User.email == "sources-admin@example.com"))
        user.is_admin = True
        session.commit()
    settings = admin.get("/api/admin/settings")
    assert settings.status_code == 200
    assert settings.json()["data"]["job_sources"] == {"linkedin": True, "naukri": True}
    saved = admin.put(
        "/api/admin/settings/job-sources",
        json={"linkedin": True, "naukri": True},
        headers=csrf_headers(admin),
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["job_sources"]["naukri"] is True
    off = admin.put(
        "/api/admin/settings/job-sources",
        json={"linkedin": False, "naukri": False},
        headers=csrf_headers(admin),
    )
    assert off.status_code == 422


def test_admin_can_save_firecrawl_key(make_user, engine):
    admin = make_user("outreach-settings@example.com")
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        user = session.scalar(select(User).where(User.email == "outreach-settings@example.com"))
        user.is_admin = True
        session.commit()
    before = admin.get("/api/admin/settings")
    assert before.json()["data"]["outreach"]["firecrawl_api_key_configured"] is False
    saved = admin.put(
        "/api/admin/settings/outreach",
        json={"firecrawl_api_key": "fc-test-key-12345"},
        headers=csrf_headers(admin),
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["outreach"]["firecrawl_api_key_configured"] is True
    assert saved.json()["data"]["outreach"]["source"] == "database"


def test_admin_can_save_elevenlabs_key(make_user, engine):
    admin = make_user("eleven-settings@example.com")
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        user = session.scalar(select(User).where(User.email == "eleven-settings@example.com"))
        user.is_admin = True
        session.commit()
    before = admin.get("/api/admin/settings")
    assert before.json()["data"]["ai"]["elevenlabs_api_key_configured"] is False
    saved = admin.put(
        "/api/admin/settings/ai",
        json={
            "enabled": False,
            "provider": "openai",
            "base_url": "https://api.openai.com/v1",
            "models": {"fast": "gpt-4o-mini", "strong": "gpt-4o", "embedding": "text-embedding-3-small"},
            "features": {
                "applications": True,
                "resume": True,
                "mock_interview": True,
                "profile_sync": True,
                "outreach": True,
            },
            "elevenlabs_api_key": "sk-test-elevenlabs-key",
            "mock_interview_voice": {
                "provider": "elevenlabs",
                "elevenlabs_agent_id": "fA4eSDsx5xNZ1RV7zEu5",
                "elevenlabs_model_id": "eleven_multilingual_v2",
            },
        },
        headers=csrf_headers(admin),
    )
    assert saved.status_code == 200, saved.text
    ai = saved.json()["data"]["ai"]
    assert ai["elevenlabs_api_key_configured"] is True
    assert ai["elevenlabs_api_key_source"] == "database"
    assert ai["mock_interview_voice"]["elevenlabs_agent_id"] == "fA4eSDsx5xNZ1RV7zEu5"


def test_admin_can_test_elevenlabs_key(make_user, engine, monkeypatch):
    admin = make_user("eleven-test@example.com")
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        user = session.scalar(select(User).where(User.email == "eleven-test@example.com"))
        user.is_admin = True
        session.commit()

    def _fake_verify(*, api_key=None, db=None):
        assert api_key == "sk-inline-eleven"
        return {"ok": True, "message": "ElevenLabs API key verified.", "tier": "starter"}

    monkeypatch.setattr("backend.app.services.elevenlabs_client.verify_credentials", _fake_verify)
    resp = admin.post(
        "/api/admin/settings/ai/test-elevenlabs",
        json={"elevenlabs_api_key": "sk-inline-eleven"},
        headers=csrf_headers(admin),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["ok"] is True


def test_admin_can_test_firecrawl_key(make_user, engine, monkeypatch):
    admin = make_user("outreach-test@example.com")
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        user = session.scalar(select(User).where(User.email == "outreach-test@example.com"))
        user.is_admin = True
        session.commit()

    def _fake_verify(*, api_key=None, db=None):
        assert api_key == "fc-test-inline"
        return {"ok": True, "message": "Firecrawl API key verified.", "remaining_credits": 100, "plan_credits": 500}

    monkeypatch.setattr(
        "backend.app.services.firecrawl_client.verify_credentials",
        _fake_verify,
    )
    resp = admin.post(
        "/api/admin/settings/outreach/test",
        json={"firecrawl_api_key": "fc-test-inline"},
        headers=csrf_headers(admin),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["ok"] is True
    assert resp.json()["data"]["remaining_credits"] == 100


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
