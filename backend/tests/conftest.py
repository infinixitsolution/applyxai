"""
Fixtures for the SaaS backend. These tests need backend/requirements.txt installed; without
it they're skipped, so the classic engine suite still runs on a plain engine install.
"""

import importlib.util

import pytest

if importlib.util.find_spec("fastapi") is None or importlib.util.find_spec("sqlalchemy") is None:
    collect_ignore_glob = ["test_*.py"]
else:
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import re

    from backend.app.api.deps import get_mailer
    from backend.app.core.config import get_settings
    from backend.app.core.cookies import CSRF_COOKIE, CSRF_HEADER
    from backend.app.core.database import build_engine, get_db
    from backend.app.core.rate_limit import RateLimiter, get_rate_limiter
    from backend.app.main import create_app
    from backend.app.models import Base

    class Outbox:
        """Captures emails instead of sending them."""

        def __init__(self):
            self.sent = []

        def send(self, email):
            self.sent.append(email)

        def last_token(self, to=None):
            for email in reversed(self.sent):
                if to is None or email.to == to:
                    match = re.search(r"token=([\w-]+)", email.body)
                    if match:
                        return match.group(1)
            raise AssertionError(f"no token email for {to}: {self.sent}")

    @pytest.fixture(autouse=True)
    def storage_dir(tmp_path, monkeypatch):
        """Uploaded files go to a per-test directory, never the real storage/."""
        path = tmp_path / "storage"
        monkeypatch.setattr(get_settings(), "STORAGE_DIR", path)
        return path

    @pytest.fixture(autouse=True)
    def default_email_settings(monkeypatch):
        """Tests assume the shipped defaults, whatever a developer's .env says."""
        settings = get_settings()
        monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", True)
        monkeypatch.setattr(settings, "SMTP_HOST", "")

    @pytest.fixture
    def outbox():
        return Outbox()

    @pytest.fixture
    def limiter():
        return RateLimiter("memory://")

    @pytest.fixture
    def engine():
        # One shared in-memory connection, so every session sees the same database.
        eng = build_engine("sqlite://", poolclass=StaticPool)
        Base.metadata.create_all(eng)
        yield eng
        eng.dispose()

    @pytest.fixture
    def db(engine):
        session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
        yield session
        session.close()

    @pytest.fixture
    def app(engine, outbox, limiter):
        application = create_app()
        application.dependency_overrides[get_mailer] = lambda: outbox
        application.dependency_overrides[get_rate_limiter] = lambda: limiter
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

        def _override_get_db():
            session = factory()
            try:
                yield session
            finally:
                session.close()

        application.dependency_overrides[get_db] = _override_get_db
        return application

    @pytest.fixture
    def api(app):
        return TestClient(app, raise_server_exceptions=False)

    def csrf_headers(client) -> dict:
        return {CSRF_HEADER: client.cookies.get(CSRF_COOKIE, "")}

    PASSWORD = "correct horse battery"

    @pytest.fixture
    def make_user(api, outbox):
        """Register + verify + log in a user through the real API; returns the client."""
        def _make(email="alice@example.com", password=PASSWORD, client=None):
            client = client or api
            assert client.post("/api/auth/register", json={"email": email, "password": password}).status_code == 202
            assert client.post("/api/auth/verify-email", json={"token": outbox.last_token(email)}).status_code == 200
            resp = client.post("/api/auth/login", json={"email": email, "password": password})
            assert resp.status_code == 200, resp.text
            return client
        return _make
