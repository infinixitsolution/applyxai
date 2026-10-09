"""Platform AI service."""

import pytest

from backend.app.core.errors import AppError
from backend.app.schemas.platform_settings import AiIn
from backend.app.services import ai_service, platform_settings_service as ps
from backend.tests.conftest import csrf_headers


def test_admin_ai_settings_round_trip(api, make_user, engine, monkeypatch):
    monkeypatch.setattr("backend.app.core.config.settings.SECRET_KEY", "x" * 32)
    admin = make_user("ai-admin@example.com")
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from backend.app.models import User

    with Session(engine) as session:
        user = session.scalar(select(User).where(User.email == "ai-admin@example.com"))
        user.is_admin = True
        session.commit()

    resp = admin.put(
        "/api/admin/settings/ai",
        json=AiIn(
            enabled=True,
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-test-key",
            models={"fast": "gpt-4o-mini", "strong": "gpt-4o", "embedding": "text-embedding-3-small"},
        ).model_dump(),
        headers=csrf_headers(admin),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]["ai"]
    assert data["enabled"] is True
    assert data["api_key_configured"] is True
    assert "sk-test" not in str(data)

    overview = admin.get("/api/admin/settings").json()["data"]
    assert overview["ai"]["ready"] is True


def test_complete_requires_feature(db, monkeypatch):
    monkeypatch.setattr("backend.app.core.config.settings.SECRET_KEY", "x" * 32)
    ps.update_ai(
        db,
        AiIn(
            enabled=False,
            api_key="sk-x",
            models={"fast": "gpt-4o-mini", "strong": "gpt-4o", "embedding": "text-embedding-3-small"},
        ),
    )
    db.commit()
    with pytest.raises(AppError) as err:
        ai_service.complete(db, ai_service.AiTask.TEST, system="s", user="u")
    assert err.value.code == "AI_DISABLED"
