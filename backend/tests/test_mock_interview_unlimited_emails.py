"""Mock interview cap bypass for allowlisted emails."""

from sqlalchemy import select

from backend.app.core.config import get_settings
from backend.app.core.plans import MOCK_INTERVIEWS_UNLIMITED
from backend.app.models import User
from backend.app.services import usage_service
from backend.app.services.auth_service import hash_password


def test_allowlisted_email_gets_unlimited_mock_interviews(db, make_user, monkeypatch):
    email = "mock-unlimited@example.com"
    make_user(email=email)
    user = db.scalar(select(User).where(User.email == email))
    assert user is not None

    monkeypatch.setenv("MOCK_INTERVIEWS_UNLIMITED_EMAILS", email)
    get_settings.cache_clear()

    limits = usage_service.plan_limits(db, user.id)
    assert limits["mock_interviews_per_month"] == MOCK_INTERVIEWS_UNLIMITED

    summary = usage_service.usage_summary(db, user.id)
    assert summary["mock_interviews"]["unlimited"] is True

    get_settings.cache_clear()


def test_db_allowlisted_email_gets_unlimited_mock_interviews(db, monkeypatch):
    from backend.app.services import platform_settings_service as ps

    email = "mock-db-only@example.com"
    user = User(email=email, password_hash=hash_password("correct horse battery"), is_verified=True)
    db.add(user)
    db.flush()

    monkeypatch.setenv("MOCK_INTERVIEWS_UNLIMITED_EMAILS", "")
    get_settings.cache_clear()
    ps.add_mock_interviews_unlimited_email(db, email)
    db.commit()

    limits = usage_service.plan_limits(db, user.id)
    assert limits["mock_interviews_per_month"] == MOCK_INTERVIEWS_UNLIMITED

    get_settings.cache_clear()
