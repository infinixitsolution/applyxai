"""
Stripe billing provider.

Live-interview sales use a one-off Payment Link. Subscription checkout is still not wired, so those
methods keep the explicit not-ready error instead of pretending a charge succeeded.

Admin stores the secret key in the same encrypted fields as Razorpay (`key_id` = publishable key,
`key_secret` = secret key, `webhook_secret` = Stripe signing secret).
"""

import hashlib
import hmac
import json
import time

import httpx

from backend.app.models import Plan, User
from backend.app.services.payments.base import (
    CheckoutConfirmation, PaymentError, RemotePayment, RemotePaymentLink, RemoteSubscription, WebhookEvent,
)

_NOT_READY = PaymentError(
    "STRIPE_NOT_READY",
    "Stripe checkout isn't fully wired yet. Use Razorpay or contact support.",
    501,
)


class StripeProvider:
    name = "stripe"

    def __init__(self, publishable_key: str, secret_key: str, webhook_secret: str) -> None:
        self.publishable_key = publishable_key
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret

    def create_plan(self, plan: Plan) -> str:
        raise _NOT_READY

    def create_subscription(self, plan: Plan, user: User) -> RemoteSubscription:
        raise _NOT_READY

    def fetch_subscription(self, subscription_id: str) -> RemoteSubscription:
        raise _NOT_READY

    def cancel_subscription(self, subscription_id: str, *, at_period_end: bool) -> RemoteSubscription:
        raise _NOT_READY

    def fetch_payment(self, payment_id: str) -> RemotePayment:
        raise _NOT_READY

    def checkout_options(self, subscription_id: str, plan: Plan, user: User) -> dict | None:
        raise _NOT_READY

    def verify_checkout(self, payment_id: str, subscription_id: str, signature: str) -> CheckoutConfirmation:
        raise _NOT_READY

    def _form(self, path: str, data: dict[str, str]) -> dict:
        try:
            response = httpx.post(
                f"https://api.stripe.com/v1{path}",
                data=data,
                auth=(self.secret_key, ""),
                timeout=20,
            )
        except httpx.HTTPError as exc:
            raise PaymentError("PAYMENTS_UNAVAILABLE", "Stripe could not be reached. Try again in a moment.", 502) from exc
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if response.status_code >= 400:
            message = ((payload.get("error") or {}).get("message")) or "Stripe rejected this payment link."
            raise PaymentError("PAYMENTS_REJECTED", str(message)[:300], 502)
        return payload

    def create_payment_link(
        self, *, amount_cents: int, currency: str, description: str, customer_name: str, customer_email: str, order_id: str,
    ) -> RemotePaymentLink:
        label = description or "Live interview"
        if customer_name:
            label = f"{label} - {customer_name}"
        price = self._form("/prices", {
            "currency": (currency or "INR").lower(),
            "unit_amount": str(int(amount_cents)),
            "product_data[name]": label[:120],
        })
        link = self._form("/payment_links", {
            "line_items[0][price]": str(price.get("id") or ""),
            "line_items[0][quantity]": "1",
            "metadata[order_id]": order_id,
            "metadata[purpose]": "live_interview",
            "payment_intent_data[metadata][order_id]": order_id,
            "payment_intent_data[metadata][purpose]": "live_interview",
            "payment_intent_data[receipt_email]": customer_email,
            "after_completion[type]": "hosted_confirmation",
        })
        return RemotePaymentLink(id=str(link.get("id") or ""), url=str(link.get("url") or ""), status="created")

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> WebhookEvent:
        if not self.webhook_secret:
            raise PaymentError("PAYMENTS_NOT_CONFIGURED", "Stripe webhook secret is not set.", 400)
        signature = headers.get("stripe-signature", "")
        parts = dict(part.split("=", 1) for part in signature.split(",") if "=" in part)
        timestamp = parts.get("t", "")
        signed = parts.get("v1", "")
        try:
            age = abs(time.time() - int(timestamp))
        except ValueError:
            age = 10**9
        expected = hmac.new(self.webhook_secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
        if not signed or age > 300 or not hmac.compare_digest(expected, signed):
            raise PaymentError("INVALID_SIGNATURE", "Invalid webhook signature.", 400)
        try:
            data = json.loads(body)
            obj = (data.get("data") or {}).get("object") or {}
            meta = obj.get("metadata") or {}
            if not isinstance(meta, dict):
                meta = {}
            event_type = str(data.get("type") or "")[:64]
            paid = event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}
            paid = paid and str(obj.get("payment_status") or "paid") in {"paid", "no_payment_required"}
            order_id = str(meta.get("order_id") or "") or None
            if meta.get("purpose") != "live_interview" or not paid:
                order_id = None
            event_id = str(data.get("id") or "") or hashlib.sha256(body).hexdigest()
            return WebhookEvent(id=event_id, type=event_type, order_id=order_id)
        except (ValueError, TypeError, AttributeError):
            raise PaymentError("INVALID_WEBHOOK", "Malformed webhook payload.", 400) from None
