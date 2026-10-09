"""
Razorpay Subscriptions over its REST API (https://razorpay.com/docs/api/payments/subscriptions/).

Checkout: the server creates the subscription, the browser opens Razorpay Checkout with its
ID, and Checkout returns razorpay_payment_id, razorpay_subscription_id, and razorpay_signature.
The signature is HMAC-SHA256(payment_id + "|" + subscription_id) with the key secret.
Webhooks carry X-Razorpay-Signature: HMAC-SHA256 of the raw body with the webhook secret.
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

import httpx

from backend.app.core.config import settings
from backend.app.models import Plan, SubscriptionStatus, User
from backend.app.services.payments.base import (
    CheckoutConfirmation, PaymentError, RemotePayment, RemoteSubscription, WebhookEvent,
)

logger = logging.getLogger("applyxai.billing")

API_BASE = "https://api.razorpay.com/v1"
# Monthly cycles the subscription may run for before Razorpay ends it (Razorpay requires a count).
TOTAL_CYCLES = 120

STATUS_MAP = {
    "created": SubscriptionStatus.PENDING,
    "authenticated": SubscriptionStatus.PENDING,
    "active": SubscriptionStatus.ACTIVE,
    "pending": SubscriptionStatus.PAST_DUE,
    "halted": SubscriptionStatus.PAST_DUE,
    "paused": SubscriptionStatus.PAST_DUE,
    "cancelled": SubscriptionStatus.CANCELLED,
    "completed": SubscriptionStatus.EXPIRED,
    "expired": SubscriptionStatus.EXPIRED,
}

_UNAVAILABLE = PaymentError("PAYMENT_PROVIDER_UNAVAILABLE",
                            "We couldn't reach the payment provider. Please try again in a minute.", 502)


def _time(value) -> datetime | None:
    return datetime.fromtimestamp(int(value), tz=timezone.utc) if value else None


def _sign(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def _subscription(entity: dict) -> RemoteSubscription:
    raw = str(entity.get("status", ""))
    return RemoteSubscription(
        id=str(entity["id"]), status=STATUS_MAP.get(raw, SubscriptionStatus.PENDING), raw_status=raw,
        plan_id=str(entity.get("plan_id") or ""), customer_id=str(entity.get("customer_id") or ""),
        current_start=_time(entity.get("current_start")), current_end=_time(entity.get("current_end")),
        notes=entity.get("notes") if isinstance(entity.get("notes"), dict) else {},
    )


def _payment(entity: dict) -> RemotePayment:
    return RemotePayment(
        id=str(entity["id"]), amount_cents=int(entity.get("amount") or 0),
        currency=str(entity.get("currency") or "INR")[:3], status=str(entity.get("status") or "")[:32],
        method=str(entity.get("method") or "")[:32], description=str(entity.get("description") or "")[:255],
        created_at=_time(entity.get("created_at")),
    )


class RazorpayProvider:
    name = "razorpay"

    def __init__(self, key_id: str, key_secret: str, webhook_secret: str, client: httpx.Client | None = None):
        if not key_id or not key_secret:
            raise PaymentError("PAYMENTS_NOT_CONFIGURED", "Online payments aren't set up yet.", 503)
        from backend.app.services.payments.razorpay_util import razorpay_mode_from_key_id, validate_key_id

        validate_key_id(key_id)
        self.key_id, self._secret, self._webhook_secret = key_id, key_secret, webhook_secret
        self.mode = razorpay_mode_from_key_id(key_id)
        self._client = client or httpx.Client(base_url=API_BASE, timeout=20)

    def __repr__(self) -> str:
        return f"RazorpayProvider(key_id={self.key_id!r})"

    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        try:
            resp = self._client.request(method, path, json=body, auth=(self.key_id, self._secret))
        except httpx.HTTPError as exc:
            logger.warning("Razorpay %s %s failed: %s", method, path, type(exc).__name__)
            raise _UNAVAILABLE from None
        if resp.status_code >= 500:
            logger.warning("Razorpay %s %s returned %s", method, path, resp.status_code)
            raise _UNAVAILABLE
        try:
            data = resp.json()
        except ValueError:
            raise _UNAVAILABLE from None
        if resp.status_code >= 400:
            # Razorpay's description is about our request (e.g. a bad plan ID), not for end users.
            logger.warning("Razorpay %s %s rejected (%s): %s", method, path, resp.status_code,
                           (data.get("error") or {}).get("description", ""))
            raise PaymentError("PAYMENT_REQUEST_REJECTED",
                               "The payment provider rejected the request. Please contact support.", 502)
        return data

    def create_plan(self, plan: Plan) -> str:
        from backend.app.services.billing_service import charge_cents
        data = self._call("POST", "/plans", {
            "period": "monthly", "interval": 1,
            "item": {"name": f"ApplyXAI {plan.name}", "amount": charge_cents(plan), "currency": plan.currency},
            "notes": {"applyxai_plan": plan.code},
        })
        return str(data["id"])

    def create_subscription(self, plan: Plan, user: User) -> RemoteSubscription:
        if not plan.provider_plan_id:
            raise PaymentError("PLAN_NOT_AVAILABLE", "This plan can't be bought online yet. Please contact support.", 503)
        return _subscription(self._call("POST", "/subscriptions", {
            "plan_id": plan.provider_plan_id, "total_count": TOTAL_CYCLES, "customer_notify": 1,
            "notes": {"user_id": str(user.id), "plan": plan.code},
        }))

    def fetch_subscription(self, subscription_id: str) -> RemoteSubscription:
        return _subscription(self._call("GET", f"/subscriptions/{subscription_id}"))

    def cancel_subscription(self, subscription_id: str, *, at_period_end: bool) -> RemoteSubscription:
        return _subscription(self._call("POST", f"/subscriptions/{subscription_id}/cancel",
                                        {"cancel_at_cycle_end": 1 if at_period_end else 0}))

    def fetch_payment(self, payment_id: str) -> RemotePayment:
        return _payment(self._call("GET", f"/payments/{payment_id}"))

    def checkout_options(self, subscription_id: str, plan: Plan, user: User) -> dict:
        from backend.app.services.payments.razorpay_util import TEST_CHECKOUT_HINT

        name = " ".join(p for p in (user.first_name, user.last_name) if p)
        opts: dict = {
            "key": self.key_id,
            "subscription_id": subscription_id,
            "name": settings.APP_NAME,
            "description": f"{plan.name} plan, billed monthly",
            "currency": plan.currency,
            "prefill": {"email": user.email, "name": name or user.email.split("@")[0]},
            "theme": {"color": "#4f46e5"},
            "modal": {"confirm_close": True, "escape": True},
            "razorpay_mode": self.mode,
        }
        if self.mode == "test":
            opts["notes"] = {"applyxai_checkout": "test"}
            opts["test_hint"] = TEST_CHECKOUT_HINT
        return opts

    def verify_credentials(self) -> dict:
        """Validate Key ID + secret against Razorpay (same API for test and live keys)."""
        from backend.app.services.payments.razorpay_util import TEST_CHECKOUT_HINT

        try:
            resp = self._client.get("/payments", params={"count": 1}, auth=(self.key_id, self._secret), timeout=20)
        except httpx.HTTPError as exc:
            logger.warning("Razorpay credential check failed: %s", type(exc).__name__)
            raise _UNAVAILABLE from None
        if resp.status_code >= 400:
            raise PaymentError("PAYMENTS_NOT_CONFIGURED", "Razorpay rejected these API keys. Check Key ID and secret.", 400)
        out = {"ok": True, "mode": self.mode, "key_id_prefix": self.key_id[:12] + "…"}
        if self.mode == "test":
            out["test_checkout_hint"] = TEST_CHECKOUT_HINT
        else:
            out["message"] = "Live keys verified. Checkout will charge real payment methods."
        return out

    def verify_checkout(self, payment_id: str, subscription_id: str, signature: str) -> CheckoutConfirmation:
        expected = _sign(self._secret, f"{payment_id}|{subscription_id}".encode())
        if not signature or not hmac.compare_digest(expected, signature):
            raise PaymentError("INVALID_PAYMENT_SIGNATURE",
                               "We couldn't confirm this payment. If you were charged, it will be applied shortly.", 400)
        return CheckoutConfirmation(subscription_id=subscription_id, payment_id=payment_id)

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> WebhookEvent:
        signature = headers.get("x-razorpay-signature", "")
        if not self._webhook_secret or not signature or not hmac.compare_digest(
                _sign(self._webhook_secret, body), signature):
            raise PaymentError("INVALID_SIGNATURE", "Invalid webhook signature.", 400)
        try:
            data = json.loads(body)
            payload = data.get("payload") or {}
            sub = ((payload.get("subscription") or {}).get("entity")) or {}
            pay = ((payload.get("payment") or {}).get("entity")) or {}
            return WebhookEvent(
                id=headers.get("x-razorpay-event-id") or hashlib.sha256(body).hexdigest(),
                type=str(data.get("event", ""))[:64],
                subscription_id=str(sub["id"]) if sub.get("id") else None,
                payment=_payment(pay) if pay.get("id") else None,
            )
        except (ValueError, TypeError, AttributeError, KeyError):
            raise PaymentError("INVALID_WEBHOOK", "Malformed webhook payload.", 400) from None
