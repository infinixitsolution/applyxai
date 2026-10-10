"""Mock interview API."""

import json

import pytest

from backend.app.schemas.platform_settings import AiIn
from backend.app.services import platform_settings_service as ps
from backend.tests.conftest import csrf_headers
from backend.tests.factories import add_application

EMAIL = "mock@example.com"


@pytest.fixture
def alice(make_user, db, monkeypatch):
    monkeypatch.setattr("backend.app.core.config.settings.SECRET_KEY", "x" * 32)
    client = make_user(EMAIL)
    ps.update_ai(
        db,
        AiIn(
            enabled=True,
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            models={"fast": "gpt-4o-mini", "strong": "gpt-4o", "embedding": "text-embedding-3-small"},
            features={"applications": True, "resume": True, "mock_interview": True},
        ),
    )
    db.commit()
    return client


@pytest.fixture
def application(db):
    return add_application(db, EMAIL, "mi1", title="Software Engineer", company="Acme", description="Python APIs")


def _mock_ai(monkeypatch):
    def fake_messages(db, task, *, messages, feature="mock_interview", temperature=0.7, max_tokens=450):
        last = messages[-1]["content"] if messages else ""
        if "Start the mock interview" in last or "Begin" in last:
            return json.dumps({"message": "Hi, tell me about yourself.", "should_end": False})
        if "candidate just answered" in last.lower() or "The candidate just answered" in last:
            return json.dumps({"message": "Thanks. What is your biggest strength?", "should_end": False})
        if "spontaneously spoken" in last.lower() or "ai_like" in last.lower():
            return json.dumps(
                {
                    "overall": "human",
                    "confidence": 80,
                    "signals": ["Personal timeline reference."],
                    "notes": "Sounds conversational.",
                }
            )
        if "Assess these" in last and "snapshot" in last.lower():
            return json.dumps(
                {
                    "overall_score": 70,
                    "facial_expression": {"score": 72, "notes": "Approachable."},
                    "eye_contact": {"score": 65, "notes": "Mostly toward camera."},
                    "grooming": {"score": 75, "notes": "Neat appearance."},
                    "presentability_summary": "Good presence for a mock call.",
                }
            )
        if "Transcript" in last and "feedback" in last.lower():
            return json.dumps(
                {
                    "overall_score": 72,
                    "dimensions": [
                        {"key": "communication", "label": "Communication", "score": 75, "notes": "Clear"},
                        {"key": "technical", "label": "Technical depth", "score": 70, "notes": "OK"},
                        {"key": "behavioral", "label": "Behavioral / STAR", "score": 68, "notes": "Add STAR"},
                        {"key": "role_fit", "label": "Role fit", "score": 74, "notes": "Good"},
                    ],
                    "strengths": ["Structured answers"],
                    "improvements": ["More metrics"],
                    "sample_answers": [{"question": "Tell me about yourself", "suggestion": "Lead with role fit."}],
                }
            )
        return json.dumps({"message": "Interesting.", "should_end": True})

    monkeypatch.setattr("backend.app.services.mock_interview_service.ai_service.complete_messages", fake_messages)
    monkeypatch.setattr(
        "backend.app.services.mock_interview_service.ai_service.synthesize_speech", lambda *a, **k: b"fake-mp3"
    )


def test_create_requires_ai_enabled(make_user, db, monkeypatch):
    monkeypatch.setattr("backend.app.core.config.settings.SECRET_KEY", "x" * 32)
    client = make_user("off@example.com")
    ps.update_ai(
        db,
        AiIn(
            enabled=False,
            api_key="sk-x",
            models={"fast": "gpt-4o-mini", "strong": "gpt-4o", "embedding": "text-embedding-3-small"},
            features={"mock_interview": False},
        ),
    )
    db.commit()
    app = add_application(db, "off@example.com", "x1")
    resp = client.post(
        "/api/mock-interviews/sessions",
        json={"application_id": str(app.id), "interview_types": ["behavioral"]},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 503


def test_full_flow(alice, application, monkeypatch):
    _mock_ai(monkeypatch)
    create = alice.post(
        "/api/mock-interviews/sessions",
        json={"application_id": str(application.id), "interview_types": ["mixed", "technical"]},
        headers=csrf_headers(alice),
    )
    assert create.status_code == 200, create.text
    sid = create.json()["data"]["id"]
    assert create.json()["data"]["interview_types"] == ["mixed"]

    opening = alice.post(f"/api/mock-interviews/sessions/{sid}/opening", headers=csrf_headers(alice))
    assert opening.status_code == 200, opening.text
    assert "tell me about yourself" in opening.json()["data"]["interviewer_message"]["content"].lower()
    assert opening.json()["data"]["audio_base64"]

    turn = alice.post(
        f"/api/mock-interviews/sessions/{sid}/turns",
        json={"content": "I am a backend engineer with five years of experience."},
        headers=csrf_headers(alice),
    )
    assert turn.status_code == 200, turn.text
    assert turn.json()["data"]["turn_count"] == 1

    detail = alice.get(f"/api/mock-interviews/sessions/{sid}")
    assert detail.status_code == 200
    assert len(detail.json()["data"]["messages"]) >= 3

    done = alice.post(f"/api/mock-interviews/sessions/{sid}/complete", headers=csrf_headers(alice))
    assert done.status_code == 200, done.text
    fb = done.json()["data"]["feedback"]
    assert fb["overall_score"] >= 50
    tech = next(d for d in fb["dimensions"] if d["key"] == "technical")
    assert tech["score"] >= 50
    assert done.json()["data"]["session"]["status"] == "completed"


def test_turn_without_inline_audio_and_tts(alice, application, monkeypatch):
    _mock_ai(monkeypatch)
    sid = alice.post(
        "/api/mock-interviews/sessions",
        json={"application_id": str(application.id), "interview_types": ["behavioral"]},
        headers=csrf_headers(alice),
    ).json()["data"]["id"]
    alice.post(f"/api/mock-interviews/sessions/{sid}/opening", headers=csrf_headers(alice))

    turn = alice.post(
        f"/api/mock-interviews/sessions/{sid}/turns?include_audio=false",
        json={"content": "I led a migration to microservices."},
        headers=csrf_headers(alice),
    )
    assert turn.status_code == 200, turn.text
    assert turn.json()["data"]["audio_base64"] == ""

    msg_id = turn.json()["data"]["interviewer_message"]["id"]
    tts = alice.post(
        f"/api/mock-interviews/sessions/{sid}/messages/{msg_id}/tts",
        json={},
        headers=csrf_headers(alice),
    )
    assert tts.status_code == 200, tts.text
    assert tts.json()["data"]["audio_base64"]


def test_availability_when_configured(alice, db):
    resp = alice.get("/api/mock-interviews/availability")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["available"] is True
    assert data["reason"] == "ready"
    presenter = data.get("presenter", {})
    assert presenter.get("mode") == "digital_human_3d"
    assert presenter.get("glb_url") == "/portrait"


def test_turn_idempotent_with_client_turn_id(alice, application, monkeypatch):
    _mock_ai(monkeypatch)
    sid = alice.post(
        "/api/mock-interviews/sessions",
        json={"application_id": str(application.id), "interview_types": ["behavioral"]},
        headers=csrf_headers(alice),
    ).json()["data"]["id"]
    alice.post(f"/api/mock-interviews/sessions/{sid}/opening", headers=csrf_headers(alice))
    turn_id = "11111111-1111-4111-8111-111111111111"
    body = {"content": "I led a migration to microservices.", "client_turn_id": turn_id}
    first = alice.post(
        f"/api/mock-interviews/sessions/{sid}/turns",
        json=body,
        headers=csrf_headers(alice),
    )
    assert first.status_code == 200, first.text
    second = alice.post(
        f"/api/mock-interviews/sessions/{sid}/turns",
        json=body,
        headers=csrf_headers(alice),
    )
    assert second.status_code == 200, second.text
    assert second.json()["data"]["turn_count"] == first.json()["data"]["turn_count"]
    assert (
        second.json()["data"]["interviewer_message"]["id"]
        == first.json()["data"]["interviewer_message"]["id"]
    )


def test_other_user_cannot_access(alice, application, make_user, monkeypatch):
    _mock_ai(monkeypatch)
    sid = alice.post(
        "/api/mock-interviews/sessions",
        json={"application_id": str(application.id), "interview_types": ["hr"]},
        headers=csrf_headers(alice),
    ).json()["data"]["id"]
    bob = make_user("bob@example.com")
    resp = bob.get(f"/api/mock-interviews/sessions/{sid}")
    assert resp.status_code == 404
