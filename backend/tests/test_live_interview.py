"""Live interview token sale through support chat, and one-use sessions."""

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.core.errors import AppError
from backend.app.models import Application, AutomationJob, Job, User
from backend.app.models.enums import ApplicationStatus, AutomationStatus
from backend.app.services import live_interview_service, platform_settings_service as ps
from backend.app.services.payments.base import RemotePaymentLink
from backend.app.services.payments.stripe_provider import StripeProvider
from backend.app.services.support_service import fulfill_order, request_live_interview
from backend.app.schemas.platform_settings import LiveInterviewSettingsIn
from backend.tests.conftest import csrf_headers


@pytest.fixture
def alice(app, db, make_user):
    client = make_user("alice@example.com", client=TestClient(app, raise_server_exceptions=False))
    client.user = db.scalar(select(User).where(User.email == "alice@example.com"))
    return client


@pytest.fixture
def admin(app, db, make_user):
    client = make_user("boss@example.com", client=TestClient(app, raise_server_exceptions=False))
    user = db.scalar(select(User).where(User.email == "boss@example.com"))
    user.is_admin = True
    db.commit()
    client.user = user
    return client


def _enable(db):
    ps.invalidate_caches()
    ps.update_live_interview(db, LiveInterviewSettingsIn(enabled=True, display_name="Live interview", price_cents=49900))
    db.commit()
    ps.invalidate_caches()


def test_request_issues_token_on_null_provider(alice, db):
    _enable(db)
    resp = alice.post("/api/support/live-interview-request", headers=csrf_headers(alice))
    assert resp.status_code == 200, resp.text
    messages = resp.json()["data"]["messages"]
    token_msgs = [m for m in messages if m["kind"] == "token"]
    assert len(token_msgs) == 1
    code = token_msgs[0]["meta"]["token"]
    assert len(code) == 8 and code.isdigit()
    assert code in token_msgs[0]["body"]


def test_token_starts_once_and_resume_until_end(alice, db):
    _enable(db)
    resp = alice.post("/api/support/live-interview-request", headers=csrf_headers(alice))
    code = next(m["meta"]["token"] for m in resp.json()["data"]["messages"] if m["kind"] == "token")
    from backend.app.services import live_interview_service
    first = live_interview_service.start_session(db, alice.user, code=code, application_id=None)
    db.commit()
    again = live_interview_service.start_session(db, alice.user, code=code, application_id=None)
    assert again["id"] == first["id"]
    ended = live_interview_service.end_session(db, alice.user, uuid.UUID(first["id"]))
    db.commit()
    assert ended["status"] == "completed"
    try:
        live_interview_service.start_session(db, alice.user, code=code, application_id=None)
        raise AssertionError("used token should not start")
    except Exception as exc:
        assert getattr(exc, "code", "") == "TOKEN_USED"


def test_support_chat_round_trip(alice, admin, db):
    sent = alice.post("/api/support/messages", json={"body": "Need help with a run"}, headers=csrf_headers(alice))
    assert sent.status_code == 200, sent.text
    inbox = admin.get("/api/admin/support/threads")
    assert inbox.status_code == 200, inbox.text
    threads = inbox.json()["data"]["threads"]
    assert threads and threads[0]["email"] == "alice@example.com"
    thread_id = threads[0]["id"]
    reply = admin.post(
        f"/api/admin/support/threads/{thread_id}/messages",
        json={"body": "Happy to help."},
        headers=csrf_headers(admin),
    )
    assert reply.status_code == 200, reply.text
    mine = alice.get("/api/support/thread")
    bodies = [m["body"] for m in mine.json()["data"]["messages"]]
    assert "Need help with a run" in bodies
    assert "Happy to help." in bodies


def _token(alice):
    resp = alice.post("/api/support/live-interview-request", headers=csrf_headers(alice))
    assert resp.status_code == 200, resp.text
    return next(m["meta"]["token"] for m in resp.json()["data"]["messages"] if m["kind"] == "token")


def test_only_auto_applied_jobs_are_listed(alice, db):
    _enable(db)
    run = AutomationJob(user_id=alice.user.id, status=AutomationStatus.COMPLETED)
    kept = Job(external_id="live-kept", title="DevOps Engineer", company="Acme")
    skipped = Job(external_id="live-skipped", title="Manual Role", company="Elsewhere")
    db.add_all([run, kept, skipped])
    db.flush()
    now = datetime.now(timezone.utc)
    db.add(Application(
        user_id=alice.user.id, job_id=kept.id, status=ApplicationStatus.APPLIED,
        automation_job_id=run.id, applied_at=now,
    ))
    db.add(Application(user_id=alice.user.id, job_id=skipped.id, status=ApplicationStatus.APPLIED, applied_at=now))
    db.commit()
    titles = [row["title"] for row in live_interview_service.list_applications(db, alice.user.id)]
    assert titles == ["DevOps Engineer"]


def test_english_transcript_keeps_english_and_drops_other_scripts():
    assert live_interview_service._english_transcript("See you later.") == "See you later."
    assert live_interview_service._english_transcript("Thank you for watching.") == ""
    assert live_interview_service._english_transcript("मैं एक DevOps engineer हूँ") == ""
    assert live_interview_service._english_transcript("Transcribe only the English words that were spoken.") == ""
    assert live_interview_service._english_transcript("Subscribe to learn English for free www.engvid.com") == ""
    assert live_interview_service._english_transcript("Thank you.") == ""
    assert live_interview_service._english_transcript("Thank you, that was a great answer.") == "Thank you, that was a great answer."


def test_scoring_failure_still_stores_the_rubric(alice, db, monkeypatch):
    _enable(db)

    def unavailable(_db):
        raise AppError("AI_DISABLED", "Platform AI is not enabled.", 503)

    monkeypatch.setattr(live_interview_service, "_ai_ready", unavailable)
    started = live_interview_service.start_session(db, alice.user, code=_token(alice), application_id=None)
    db.commit()
    ended = live_interview_service.end_session(db, alice.user, uuid.UUID(started["id"]))
    assert ended["status"] == "completed"
    assert len(ended["feedback"]["rubric_scores"]) == 100
    assert ended["feedback"]["overall_score"] == 0
    with pytest.raises(AppError) as caught:
        live_interview_service.regenerate_report(db, alice.user, uuid.UUID(started["id"]))
    assert caught.value.code == "AI_DISABLED"
    kept = live_interview_service.get_session(db, alice.user.id, uuid.UUID(started["id"]))
    assert kept["feedback"]["summary"] == ended["feedback"]["summary"]


def test_regenerate_replaces_the_saved_report(alice, db, monkeypatch):
    _enable(db)
    monkeypatch.setattr(live_interview_service, "_ai_ready", lambda _db: None)
    monkeypatch.setattr(
        live_interview_service, "complete",
        lambda *args, **kwargs: json.dumps({
            "overall_score": 81,
            "summary": "Clear answers.",
            "knowledge_summary": "Clear answers.",
            "rubric_scores": [],
            "strengths": ["Direct"],
            "suggestions": ["Add an example"],
            "dimensions": [],
            "sample_answers": [],
            "question_breakdown": [],
        }),
    )
    started = live_interview_service.start_session(db, alice.user, code=_token(alice), application_id=None)
    session = db.get(live_interview_service.LiveInterviewSession, uuid.UUID(started["id"]))
    session.transcript = [{
        "role": "candidate",
        "text": "I built the deployment pipeline on AWS and Kubernetes last year.",
        "at": datetime.now(timezone.utc).isoformat(),
    }]
    db.commit()
    live_interview_service.end_session(db, alice.user, uuid.UUID(started["id"]))
    db.commit()
    again = live_interview_service.regenerate_report(db, alice.user, uuid.UUID(started["id"]))
    assert again["feedback"]["summary"] == "Clear answers."
    assert again["feedback"]["overall_score"] == 81
    assert len(again["feedback"]["rubric_scores"]) == 100


def test_deferred_clip_then_streamed_answer_is_saved_after_the_question(alice, db, monkeypatch):
    _enable(db)
    monkeypatch.setattr(live_interview_service, "_ai_ready", lambda _db: None)
    monkeypatch.setattr(
        live_interview_service, "transcribe_audio",
        lambda *a, **k: "Tell me about a production incident you handled.",
    )
    monkeypatch.setattr(live_interview_service, "stream_complete", lambda *a, **k: iter(["I fixed ", "the cache."]))
    started = live_interview_service.start_session(db, alice.user, code=_token(alice), application_id=None)
    session_id = uuid.UUID(started["id"])
    clip = live_interview_service.add_clip(
        db, alice.user, session_id, speaker="interviewer", audio=b"wav", filename="clip.wav", defer_answer=True,
    )
    db.commit()
    assert clip["answer_pending"] is True
    assert [t["role"] for t in clip["transcript"]] == ["interviewer"]

    streamed = "".join(live_interview_service.stream_answer(db, alice.user, session_id))
    assert streamed == "I fixed the cache."
    db.expire_all()
    saved = live_interview_service.get_session(db, alice.user.id, session_id)["transcript"]
    assert [(t["role"], t["text"]) for t in saved][-1] == ("suggestion", "I fixed the cache.")
    with pytest.raises(AppError) as caught:
        live_interview_service.stream_answer(db, alice.user, session_id)
    assert caught.value.code == "NO_QUESTION"


def test_payment_link_issues_the_token_after_fulfillment(alice, db):
    _enable(db)

    class FakeProvider:
        name = "razorpay"

        def create_payment_link(self, **kwargs):
            self.order_id = kwargs["order_id"]
            return RemotePaymentLink(id="plink_1", url="https://pay.example/1", status="created")

    provider = FakeProvider()
    request_live_interview(db, alice.user, provider)
    db.commit()
    assert fulfill_order(db, provider.order_id) is True
    db.commit()
    messages = alice.get("/api/support/thread").json()["data"]["messages"]
    token = next(message for message in messages if message["kind"] == "token")
    assert token["meta"]["token_status"] == "unused"
    assert len(token["meta"]["token"]) == 8


def test_stripe_webhook_accepts_a_paid_live_interview():
    secret = "whsec_test"
    order_id = "11111111-1111-1111-1111-111111111111"
    body = json.dumps({
        "id": "evt_1",
        "type": "checkout.session.completed",
        "data": {"object": {
            "payment_status": "paid",
            "metadata": {"purpose": "live_interview", "order_id": order_id},
        }},
    }).encode()
    stamp = str(int(time.time()))
    signature = hmac.new(secret.encode(), f"{stamp}.".encode() + body, hashlib.sha256).hexdigest()
    event = StripeProvider("pk_test", "sk_test", secret).parse_webhook(
        {"stripe-signature": f"t={stamp},v1={signature}"}, body,
    )
    assert event.order_id == order_id
    with pytest.raises(AppError) as caught:
        StripeProvider("pk_test", "sk_test", secret).parse_webhook({"stripe-signature": "t=1,v1=nope"}, body)
    assert caught.value.code == "INVALID_SIGNATURE"
