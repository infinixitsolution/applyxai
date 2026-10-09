"""
Billing with the real Razorpay provider class talking to an in-memory fake of Razorpay's API
(httpx.MockTransport), plus the development-only null provider. No network is used.
"""

import hashlib
import hmac
import itertools
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.models import BillingEvent, Payment, Plan, Subscription, SubscriptionStatus
from backend.app.services import billing_service
from backend.app.services.payments import get_payment_provider
from backend.app.services.payments.null import NullProvider
from backend.app.services.payments.razorpay import API_BASE, RazorpayProvider
from backend.tests.conftest import csrf_headers

KEY_ID, SECRET, WEBHOOK_SECRET = "rzp_test_key", "test-secret", "webhook-secret"
DAY = 86400


class FakeRazorpay:
    """Just enough of api.razorpay.com/v1 for subscriptions."""

    def __init__(self):
        self.plans, self.subs, self.payments, self.calls = {}, {}, {}, []
        self.down = False
        self._ids = itertools.count(1)

    def _id(self, prefix):
        return f"{prefix}_{next(self._ids):06d}"

    def handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        path = request.url.path.removeprefix("/v1")
        self.calls.append((request.method, path, body))
        if self.down:
            return httpx.Response(503, json={"error": {"description": "down"}})
        assert request.headers["authorization"].startswith("Basic ")
        parts = path.strip("/").split("/")
        if request.method == "POST" and parts == ["plans"]:
            plan = {"id": self._id("plan"), **body}
            self.plans[plan["id"]] = plan
            return httpx.Response(200, json=plan)
        if request.method == "POST" and parts == ["subscriptions"]:
            if body["plan_id"] not in self.plans:
                return httpx.Response(400, json={"error": {"description": "The id provided does not exist"}})
            sub = {"id": self._id("sub"), "entity": "subscription", "plan_id": body["plan_id"], "status": "created",
                   "customer_id": None, "current_start": None, "current_end": None, "notes": body["notes"]}
            self.subs[sub["id"]] = sub
            return httpx.Response(200, json=sub)
        if parts[0] == "subscriptions" and parts[1] in self.subs:
            sub = self.subs[parts[1]]
            if request.method == "POST" and parts[2:] == ["cancel"]:
                if not body["cancel_at_cycle_end"]:
                    sub["status"] = "cancelled"
            return httpx.Response(200, json=sub)
        if parts[0] == "payments" and parts[1] in self.payments:
            return httpx.Response(200, json=self.payments[parts[1]])
        return httpx.Response(404, json={"error": {"description": "not found"}})

    # What happens at Razorpay when the customer pays, or a renewal fails.
    def charge(self, sub_id) -> str:
        sub, now = self.subs[sub_id], int(time.time())
        sub.update(status="active", customer_id="cust_1", current_start=now, current_end=now + 30 * DAY)
        plan = self.plans[sub["plan_id"]]
        pay = {"id": self._id("pay"), "entity": "payment", "amount": plan["item"]["amount"], "currency": "INR",
               "status": "captured", "method": "upi", "created_at": now}
        self.payments[pay["id"]] = pay
        return pay["id"]

    def cancel_calls(self):
        return [(path, body) for method, path, body in self.calls if path.endswith("/cancel")]


def checkout_signature(payment_id, sub_id, secret=SECRET):
    return hmac.new(secret.encode(), f"{payment_id}|{sub_id}".encode(), hashlib.sha256).hexdigest()


@pytest.fixture
def razorpay(app, db):
    fake = FakeRazorpay()
    provider = RazorpayProvider(KEY_ID, SECRET, WEBHOOK_SECRET, client=httpx.Client(
        base_url=API_BASE, transport=httpx.MockTransport(fake.handle)))
    app.dependency_overrides[get_payment_provider] = lambda: provider
    billing_service.sync_provider_plans(db, provider)
    db.commit()
    fake.provider = provider
    return fake


@pytest.fixture
def null_provider(app):
    app.dependency_overrides[get_payment_provider] = lambda: NullProvider()


@pytest.fixture
def alice(make_user):
    return make_user("alice@example.com")


def post(client, path, body=None):
    return client.post(f"/api/billing{path}", json=body, headers=csrf_headers(client))


def plan_of(client):
    return client.get("/api/usage").json()["data"]["plan"]


def buy(client, fake, plan="starter"):
    """Checkout in the browser, pay at Razorpay, confirm on our server."""
    started = post(client, "/checkout", {"plan": plan})
    assert started.status_code == 200, started.text
    sub_id = started.json()["data"]["checkout"]["subscription_id"]
    pay_id = fake.charge(sub_id)
    confirmed = post(client, "/confirm", {"payment_id": pay_id, "subscription_id": sub_id,
                                          "signature": checkout_signature(pay_id, sub_id)})
    return sub_id, pay_id, confirmed


def webhook(app, event, sub_id=None, payment=None, *, event_id=None, secret=WEBHOOK_SECRET):
    payload = {}
    if sub_id:
        payload["subscription"] = {"entity": {"id": sub_id, "status": "active"}}
    if payment:
        payload["payment"] = {"entity": payment}
    body = json.dumps({"entity": "event", "event": event, "payload": payload}).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    headers = {"X-Razorpay-Signature": signature, "X-Razorpay-Event-Id": event_id or f"evt_{time.time_ns()}",
               "Content-Type": "application/json"}
    return TestClient(app).post("/api/billing/webhook/razorpay", content=body, headers=headers)


# ----------------------------------------------------------------------------- plans
def test_sync_plans_creates_paid_plans_once(db, razorpay):
    plans = {p.code: p for p in db.query(Plan).all()}
    assert set(plans) == {"free", "starter", "pro", "premium", "campus", "campus_pro"}
    assert plans["free"].provider_plan_id == "" and plans["pro"].provider_plan_id.startswith("plan_")
    created = razorpay.plans[plans["pro"].provider_plan_id]
    assert created["period"] == "monthly" and created["item"]["amount"] == plans["pro"].price_cents
    campus = razorpay.plans[plans["campus"].provider_plan_id]
    assert campus["item"]["amount"] == plans["campus"].price_cents * plans["campus"].limits["seats"]
    assert billing_service.sync_provider_plans(db, razorpay.provider) == []


# ----------------------------------------------------------------------------- razorpay checkout
def test_checkout_then_verified_payment_activates_the_plan(app, alice, razorpay, db):
    started = post(alice, "/checkout", {"plan": "starter"})
    assert started.status_code == 200
    data = started.json()["data"]
    assert data["checkout"]["key"] == KEY_ID and data["checkout"]["prefill"]["email"] == "alice@example.com"
    assert data["subscription"]["status"] == "pending" and data["replaces"] is None
    assert plan_of(alice) == "free"
    assert alice.get("/api/billing").json()["data"]["pending"]["plan"]["code"] == "starter"

    sub_id = data["checkout"]["subscription_id"]
    pay_id = razorpay.charge(sub_id)
    confirmed = post(alice, "/confirm", {"payment_id": pay_id, "subscription_id": sub_id,
                                         "signature": checkout_signature(pay_id, sub_id)})
    assert confirmed.status_code == 200 and confirmed.json()["data"]["subscription"]["status"] == "active"
    assert plan_of(alice) == "starter"
    assert alice.get("/api/usage").json()["data"]["applications"]["limit"] == 100

    overview = alice.get("/api/billing").json()["data"]
    assert overview["provider"] == "razorpay" and overview["pending"] is None
    assert overview["subscription"]["current_period_end"] is not None
    assert overview["payments"][0]["amount_cents"] == db.query(Plan).filter_by(code="starter").one().price_cents
    assert overview["payments"][0]["status"] == "captured"
    notes = [n["type"] for n in alice.get("/api/notifications").json()["data"]["items"]]
    assert "plan_active" in notes


def test_a_forged_or_unpaid_confirmation_grants_nothing(alice, razorpay):
    sub_id = post(alice, "/checkout", {"plan": "pro"}).json()["data"]["checkout"]["subscription_id"]
    forged = post(alice, "/confirm", {"payment_id": "pay_x", "subscription_id": sub_id, "signature": "0" * 64})
    assert forged.status_code == 400 and forged.json()["error"]["code"] == "INVALID_PAYMENT_SIGNATURE"
    assert plan_of(alice) == "free"

    # A correctly signed callback still isn't enough: the subscription is re-read from Razorpay.
    razorpay.payments["pay_unpaid"] = {"id": "pay_unpaid", "amount": 1, "currency": "INR", "status": "failed"}
    unpaid = post(alice, "/confirm", {"payment_id": "pay_unpaid", "subscription_id": sub_id,
                                      "signature": checkout_signature("pay_unpaid", sub_id)})
    assert unpaid.status_code == 200 and unpaid.json()["data"]["subscription"]["status"] == "pending"
    assert plan_of(alice) == "free"


def test_checkout_rules(alice, razorpay):
    assert post(alice, "/checkout", {"plan": "free"}).json()["error"]["code"] == "FREE_PLAN"
    assert post(alice, "/checkout", {"plan": "gold"}).status_code == 404
    buy(alice, razorpay, "starter")
    again = post(alice, "/checkout", {"plan": "starter"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "ALREADY_SUBSCRIBED"


def test_switching_plans_replaces_the_old_subscription_at_once(alice, razorpay, db):
    old_sub, _, _ = buy(alice, razorpay, "starter")
    started = post(alice, "/checkout", {"plan": "pro"}).json()["data"]
    assert started["replaces"]["plan"]["code"] == "starter"
    assert plan_of(alice) == "starter"                       # nothing changes until the new payment is verified

    new_sub = started["checkout"]["subscription_id"]
    pay_id = razorpay.charge(new_sub)
    post(alice, "/confirm", {"payment_id": pay_id, "subscription_id": new_sub,
                             "signature": checkout_signature(pay_id, new_sub)})
    assert plan_of(alice) == "pro"
    assert razorpay.cancel_calls() == [(f"/subscriptions/{old_sub}/cancel", {"cancel_at_cycle_end": 0})]
    old = db.query(Subscription).filter_by(provider_subscription_id=old_sub).one()
    db.refresh(old)
    assert old.status == SubscriptionStatus.CANCELLED


def test_cancel_keeps_the_plan_until_the_period_ends(app, alice, razorpay):
    assert post(alice, "/cancel").json()["error"]["code"] == "NO_SUBSCRIPTION"
    sub_id, _, _ = buy(alice, razorpay)
    cancelled = post(alice, "/cancel").json()["data"]["subscription"]
    assert cancelled["cancel_at_period_end"] is True and cancelled["status"] == "active"
    assert razorpay.cancel_calls() == [(f"/subscriptions/{sub_id}/cancel", {"cancel_at_cycle_end": 1})]
    assert plan_of(alice) == "starter"
    post(alice, "/cancel")
    assert len(razorpay.cancel_calls()) == 1                 # cancelling twice is harmless

    razorpay.subs[sub_id]["status"] = "cancelled"            # the period ends at Razorpay
    assert webhook(app, "subscription.cancelled", sub_id).status_code == 200
    assert plan_of(alice) == "free"
    notes = [n["type"] for n in alice.get("/api/notifications").json()["data"]["items"]]
    assert "plan_cancelled" in notes and "plan_ended" in notes


# ----------------------------------------------------------------------------- webhooks
def test_webhooks_need_a_valid_signature(app, alice, razorpay, db):
    sub_id = post(alice, "/checkout", {"plan": "starter"}).json()["data"]["checkout"]["subscription_id"]
    razorpay.charge(sub_id)
    bad = webhook(app, "subscription.activated", sub_id, secret="wrong")
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "INVALID_SIGNATURE"
    assert plan_of(alice) == "free" and db.query(BillingEvent).count() == 0


def test_a_webhook_activates_a_paid_checkout_the_browser_never_confirmed(app, alice, razorpay, db):
    sub_id = post(alice, "/checkout", {"plan": "starter"}).json()["data"]["checkout"]["subscription_id"]
    pay_id = razorpay.charge(sub_id)
    payment = razorpay.payments[pay_id]
    first = webhook(app, "subscription.charged", sub_id, payment, event_id="evt_1")
    assert first.status_code == 200 and first.json()["data"] == {"duplicate": False, "matched": True}
    assert plan_of(alice) == "starter"
    again = webhook(app, "subscription.charged", sub_id, payment, event_id="evt_1")
    assert again.json()["data"] == {"duplicate": True}
    assert db.query(Payment).count() == 1 and db.query(BillingEvent).count() == 1


def test_webhook_payloads_are_not_trusted_for_status(app, alice, razorpay):
    sub_id, _, _ = buy(alice, razorpay)
    razorpay.subs[sub_id]["status"] = "cancelled"
    # A late "activated" event carries an old status; the current one is read from Razorpay.
    webhook(app, "subscription.activated", sub_id)
    assert plan_of(alice) == "free"


def test_a_failed_renewal_drops_to_free_and_tells_the_user(app, alice, razorpay):
    sub_id, _, _ = buy(alice, razorpay)
    razorpay.subs[sub_id]["status"] = "pending"
    webhook(app, "subscription.pending", sub_id)
    assert plan_of(alice) == "free"
    assert alice.get("/api/billing").json()["data"]["subscription"] is None
    assert "payment_failed" in [n["type"] for n in alice.get("/api/notifications").json()["data"]["items"]]
    razorpay.subs[sub_id]["status"] = "active"               # the retry succeeds
    webhook(app, "subscription.charged", sub_id)
    assert plan_of(alice) == "starter"


def test_unknown_subscriptions_are_recorded_and_ignored(app, razorpay, db):
    resp = webhook(app, "subscription.activated", "sub_someone_else")
    assert resp.json()["data"] == {"duplicate": False, "matched": False}
    assert db.query(BillingEvent).count() == 1


def test_when_razorpay_is_unreachable_the_webhook_fails_so_it_is_retried(app, alice, razorpay, db):
    sub_id = post(alice, "/checkout", {"plan": "starter"}).json()["data"]["checkout"]["subscription_id"]
    razorpay.charge(sub_id)
    razorpay.down = True
    failed = webhook(app, "subscription.charged", sub_id, event_id="evt_retry")
    assert failed.status_code == 502 and failed.json()["error"]["code"] == "PAYMENT_PROVIDER_UNAVAILABLE"
    assert db.query(BillingEvent).count() == 0               # not marked as processed
    razorpay.down = False
    assert webhook(app, "subscription.charged", sub_id, event_id="evt_retry").json()["data"]["matched"] is True
    assert plan_of(alice) == "starter"


# ----------------------------------------------------------------------------- isolation
def test_users_cannot_confirm_or_see_each_others_billing(app, make_user, alice, razorpay):
    sub_id, pay_id, _ = buy(alice, razorpay)
    bob = make_user("bob@example.com", client=TestClient(app))
    stolen = post(bob, "/confirm", {"payment_id": pay_id, "subscription_id": sub_id,
                                    "signature": checkout_signature(pay_id, sub_id)})
    assert stolen.status_code == 404
    data = bob.get("/api/billing").json()["data"]
    assert data["subscription"] is None and data["payments"] == []
    assert plan_of(bob) == "free" and plan_of(alice) == "starter"


def test_billing_needs_a_login_and_csrf(app, alice, razorpay):
    assert TestClient(app).get("/api/billing").status_code == 401
    no_csrf = alice.post("/api/billing/checkout", json={"plan": "starter"})
    assert no_csrf.status_code == 403


# ----------------------------------------------------------------------------- null provider
def test_null_checkout_is_blocked_without_dev_instant_flag(app, alice, null_provider):
    resp = post(alice, "/checkout", {"plan": "starter"})
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "CHECKOUT_DISABLED"


def test_null_provider_grants_plans_instantly_for_development(app, alice, null_provider, monkeypatch):
    monkeypatch.setattr("backend.app.services.billing_service.settings.PAYMENT_DEV_INSTANT_CHECKOUT", True)
    started = post(alice, "/checkout", {"plan": "pro"}).json()["data"]
    assert started["checkout"] is None and started["subscription"]["status"] == "active"
    assert plan_of(alice) == "pro"
    post(alice, "/checkout", {"plan": "starter"})
    assert plan_of(alice) == "starter"
    assert post(alice, "/cancel").json()["data"]["subscription"]["cancel_at_period_end"] is True
    assert alice.get("/api/billing").json()["data"]["provider"] == "null"
    assert TestClient(app).post("/api/billing/webhook/razorpay", content=b"{}").status_code == 404


def test_plans_endpoint_reads_the_seeded_table(api, razorpay, db):
    db.query(Plan).filter_by(code="pro").one().price_cents = 123400
    db.commit()
    plans = {p["code"]: p for p in api.get("/api/plans").json()["data"]["plans"]}
    assert plans["pro"]["price_cents"] == 123400 and list(plans) == ["free", "starter", "pro", "premium"]
