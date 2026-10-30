"""GST issue, candidate referrals, Stripe checkout webhook, Naukri default, poll heartbeat."""

import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from backend.app.core.platform_defaults import DEFAULT_JOB_SOURCES
from backend.app.models import Payment, PlatformSettings, User
from backend.app.services import automation_settings_service, candidate_referral_service, gst_service
from backend.app.services.payments.stripe_provider import StripeProvider
from backend.tests.test_automation_api import claim, make_ready, pair, start


def test_naukri_is_on_by_default():
    assert DEFAULT_JOB_SOURCES["naukri"] is True
    assert DEFAULT_JOB_SOURCES["linkedin"] is True


def test_linkedin_connect_defaults_off():
    assert automation_settings_service._DEFAULTS["connect_hr"] is False


def test_gst_issue_for_captured_payment(db):
    user = User(email="gst-pay@example.com", password_hash="x", is_verified=True)
    db.add(user)
    db.flush()
    row = db.get(PlatformSettings, "default")
    if row is None:
        row = PlatformSettings(key="default")
        db.add(row)
    row.gst = {
        "enabled": True,
        "gstin": "29AABCU9603R1ZM",
        "legal_name": "ApplyXAI",
        "state_code": "29",
        "rate_percent": 18,
        "pricing_tax_exclusive": True,
        "invoice_prefix": "AX",
        "invoice_next_number": 1,
    }
    pay = Payment(
        user_id=user.id,
        provider="razorpay",
        provider_payment_id="pay_leftover_1",
        amount_cents=49900,
        currency="INR",
        status="captured",
        description="Starter plan",
    )
    db.add(pay)
    db.flush()
    inv = gst_service.issue_for_payment(db, pay)
    assert inv is not None
    assert inv.status == "issued"
    assert inv.total_cents > 0
    pdf = gst_service.invoice_pdf_bytes(inv)
    assert pdf.startswith(b"%PDF")


def test_candidate_referral_attribute(db):
    referrer = User(email="ref-from@example.com", password_hash="x", is_verified=True)
    referred = User(email="ref-to@example.com", password_hash="x", is_verified=True)
    db.add_all([referrer, referred])
    db.flush()
    code = candidate_referral_service.ensure_user_code(db, referrer)
    row = candidate_referral_service.attribute_on_register(db, referred=referred, code=code)
    assert row is not None
    assert row.referrer_user_id == referrer.id
    candidate_referral_service.mark_converted(db, referred.id)
    db.refresh(row)
    assert row.status == "converted"
    summary = candidate_referral_service.summary_for(db, referrer)
    assert summary["converted"] == 1


def test_stripe_checkout_session_webhook_parses_subscription():
    secret = "whsec_test"
    payload = {
        "id": "evt_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_1",
                "object": "checkout.session",
                "payment_status": "paid",
                "subscription": "sub_test_1",
                "payment_intent": "pi_test_1",
                "amount_total": 49900,
                "currency": "inr",
                "metadata": {"plan": "starter"},
            }
        },
    }
    body = json.dumps(payload).encode()
    stamp = str(int(time.time()))
    signature = hmac.new(secret.encode(), f"{stamp}.".encode() + body, hashlib.sha256).hexdigest()
    event = StripeProvider("pk_test", "sk_test", secret).parse_webhook(
        {"stripe-signature": f"t={stamp},v1={signature}"},
        body,
    )
    assert event.subscription_id == "cs_test_1"
    assert event.payment is not None
    assert event.payment.status == "captured"


@pytest.fixture
def leftover_alice(app, make_user):
    return make_ready(make_user("leftover-alice@example.com", client=TestClient(app)))


@pytest.fixture
def leftover_agent(app, leftover_alice):
    return pair(app, leftover_alice)


def test_poll_heartbeat_includes_profile_timestamps(leftover_alice, leftover_agent):
    run_id = start(leftover_alice).json()["data"]["id"]
    payload = claim(leftover_agent)
    assert payload and payload["id"] == run_id
    busy = leftover_agent.post("/api/agent/poll", json={"active_run_id": run_id}).json()["data"]
    assert busy["run"] is None
    assert busy.get("heartbeat") is True
    assert "profile_updated_at" in busy
    assert "qa_updated_at" in busy
