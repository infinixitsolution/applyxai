"""
Stripe billing provider.

Live-interview sales use a one-off Payment Link. Subscriptions use Checkout Sessions
(mode=subscription). Admin stores the secret key in the same encrypted fields as Razorpay
(`key_id` = publishable key, `key_secret` = secret key, `webhook_secret` = Stripe signing secret).
"""

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone

import httpx

from backend.app.core.config import settings
from backend.app.models import Plan, SubscriptionStatus, User
from backend.app.services.payments.base import (
    CheckoutConfirmation, PaymentError, RemotePayment, RemotePaymentLink, RemoteSubscription, WebhookEvent,
)

logger = logging.getLogger("applyxai.billing")

STATUS_MAP = {
    "incomplete": SubscriptionStatus.PENDING,
    "incomplete_expired": SubscriptionStatus.EXPIRED,
    "trialing": SubscriptionStatus.TRIALING,
    "active": SubscriptionStatus.ACTIVE,
    "past_due": SubscriptionStatus.PAST_DUE,
    "canceled": SubscriptionStatus.CANCELLED,
    "unpaid": SubscriptionStatus.PAST_DUE,
    "paused": SubscriptionStatus.PAST_DUE,
}


class StripeProvider:
    name = "stripe"

    def __init__(self, publishable_key: str, secret_key: str, webhook_secret: str) -> None:
        self.publishable_key = publishable_key
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret

    def _form(self, path: str, data: dict[str, str] | None = None, *, method: str = "POST") -> dict:
        try:
            response = httpx.request(
                method,
                f"https://api.stripe.com/v1{path}",
                data=data or None,
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
            message = ((payload.get("error") or {}).get("message")) or "Stripe rejected this request."
            raise PaymentError("PAYMENTS_REJECTED", str(message)[:300], 502)
        return payload

    def _get(self, path: str) -> dict:
        return self._form(path, method="GET")

    def create_plan(self, plan: Plan) -> str:
        from backend.app.services.billing_service import charge_cents

        product = self._form("/products", {
            "name": f"ApplyXAI {plan.name}",
            "metadata[applyxai_plan]": plan.code,
        })
        price = self._form("/prices", {
            "currency": (plan.currency or "INR").lower(),
            "unit_amount": str(int(charge_cents(plan))),
            "recurring[interval]": "month",
            "product": str(product.get("id") or ""),
            "metadata[applyxai_plan]": plan.code,
        })
        return str(price.get("id") or "")

    def _ensure_customer(self, user: User) -> str:
        name = " ".join(p for p in (user.first_name, user.last_name) if p)
        customer = self._form("/customers", {
            "email": user.email,
            "name": name or user.email.split("@")[0],
            "metadata[user_id]": str(user.id),
        })
        return str(customer.get("id") or "")

    def create_subscription(self, plan: Plan, user: User) -> RemoteSubscription:
        if not (plan.provider_plan_id or "").strip():
            raise PaymentError(
                "PLAN_NOT_AVAILABLE",
                "This plan is not linked to Stripe yet. An admin must run Sync plans in Settings → Payments.",
                503,
            )
        customer_id = self._ensure_customer(user)
        success = (settings.FRONTEND_URL or "").rstrip("/") + "/app/billing?checkout=success&session_id={CHECKOUT_SESSION_ID}"
        cancel = (settings.FRONTEND_URL or "").rstrip("/") + "/app/billing?checkout=cancel"
        session = self._form("/checkout/sessions", {
            "mode": "subscription",
            "customer": customer_id,
            "line_items[0][price]": plan.provider_plan_id,
            "line_items[0][quantity]": "1",
            "success_url": success,
            "cancel_url": cancel,
            "client_reference_id": str(user.id),
            "metadata[user_id]": str(user.id),
            "metadata[plan]": plan.code,
            "subscription_data[metadata][user_id]": str(user.id),
            "subscription_data[metadata][plan]": plan.code,
        })
        return RemoteSubscription(
            id=str(session.get("id") or ""),
            status=SubscriptionStatus.PENDING,
            raw_status=str(session.get("status") or "open"),
            plan_id=plan.provider_plan_id,
            customer_id=customer_id,
            notes={"checkout_url": str(session.get("url") or ""), "session_id": str(session.get("id") or "")},
        )

    def _subscription(self, entity: dict) -> RemoteSubscription:
        raw = str(entity.get("status") or "")
        period = entity.get("items", {}).get("data", [{}])[0].get("current_period") if isinstance(entity.get("items"), dict) else None
        start = entity.get("current_period_start")
        end = entity.get("current_period_end")
        if isinstance(period, dict):
            start = period.get("start") or start
            end = period.get("end") or end
        return RemoteSubscription(
            id=str(entity.get("id") or ""),
            status=STATUS_MAP.get(raw, SubscriptionStatus.PENDING),
            raw_status=raw,
            plan_id=str((((entity.get("items") or {}).get("data") or [{}])[0].get("price") or {}).get("id") or ""),
            customer_id=str(entity.get("customer") or ""),
            current_start=datetime.fromtimestamp(int(start), tz=timezone.utc) if start else None,
            current_end=datetime.fromtimestamp(int(end), tz=timezone.utc) if end else None,
        )

    def fetch_subscription(self, subscription_id: str) -> RemoteSubscription:
        if subscription_id.startswith("cs_"):
            session = self._get(f"/checkout/sessions/{subscription_id}")
            sub_id = str(session.get("subscription") or "")
            if sub_id:
                return self._subscription(self._get(f"/subscriptions/{sub_id}"))
            return RemoteSubscription(
                id=subscription_id,
                status=SubscriptionStatus.ACTIVE if session.get("payment_status") == "paid" else SubscriptionStatus.PENDING,
                raw_status=str(session.get("status") or ""),
                customer_id=str(session.get("customer") or ""),
                notes={"checkout_url": str(session.get("url") or "")},
            )
        return self._subscription(self._get(f"/subscriptions/{subscription_id}"))

    def cancel_subscription(self, subscription_id: str, *, at_period_end: bool) -> RemoteSubscription:
        if subscription_id.startswith("cs_"):
            remote = self.fetch_subscription(subscription_id)
            subscription_id = remote.id
        return self._subscription(self._form(
            f"/subscriptions/{subscription_id}",
            {"cancel_at_period_end": "true" if at_period_end else "false"},
        ))

    def fetch_payment(self, payment_id: str) -> RemotePayment:
        if payment_id.startswith("pi_"):
            intent = self._get(f"/payment_intents/{payment_id}")
            return RemotePayment(
                id=str(intent.get("id") or payment_id),
                amount_cents=int(intent.get("amount") or 0),
                currency=str(intent.get("currency") or "inr").upper()[:3],
                status="captured" if str(intent.get("status") or "") in {"succeeded"} else str(intent.get("status") or "")[:32],
                method="card",
                description=str((intent.get("description") or ""))[:255],
            )
        charge = self._get(f"/charges/{payment_id}")
        return RemotePayment(
            id=str(charge.get("id") or payment_id),
            amount_cents=int(charge.get("amount") or 0),
            currency=str(charge.get("currency") or "inr").upper()[:3],
            status="captured" if charge.get("paid") else str(charge.get("status") or "")[:32],
            method=str((charge.get("payment_method_details") or {}).get("type") or "")[:32],
            description=str(charge.get("description") or "")[:255],
        )

    def checkout_options(self, subscription_id: str, plan: Plan, user: User) -> dict | None:
        url = ""
        if subscription_id.startswith("cs_"):
            session = self._get(f"/checkout/sessions/{subscription_id}")
            url = str(session.get("url") or "")
        name = " ".join(p for p in (user.first_name, user.last_name) if p)
        return {
            "provider": "stripe",
            "key": self.publishable_key,
            "publishable_key": self.publishable_key,
            "subscription_id": subscription_id,
            "session_id": subscription_id,
            "url": url,
            "name": settings.APP_NAME,
            "description": f"{plan.name} plan, billed monthly",
            "currency": plan.currency,
            "prefill": {"email": user.email, "name": name or user.email.split("@")[0]},
        }

    def verify_checkout(self, payment_id: str, subscription_id: str, signature: str) -> CheckoutConfirmation:
        session_id = subscription_id or payment_id
        session = self._get(f"/checkout/sessions/{session_id}")
        paid = str(session.get("payment_status") or "") in {"paid", "no_payment_required"}
        if not paid:
            raise PaymentError("PAYMENT_PENDING", "Stripe Checkout has not completed yet.", 409)
        sub_id = str(session.get("subscription") or session_id)
        pay_id = str(session.get("payment_intent") or session.get("id") or payment_id)
        return CheckoutConfirmation(subscription_id=sub_id, payment_id=pay_id)

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
            event_id = str(data.get("id") or "") or hashlib.sha256(body).hexdigest()

            order_id = str(meta.get("order_id") or "") or None
            paid = event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}
            paid = paid and str(obj.get("payment_status") or "paid") in {"paid", "no_payment_required"}
            if meta.get("purpose") != "live_interview" or not paid:
                if meta.get("purpose") != "live_interview":
                    order_id = None

            subscription_id = None
            payment = None
            if event_type.startswith("customer.subscription."):
                subscription_id = str(obj.get("id") or "") or None
            elif event_type.startswith("checkout.session."):
                # Pending local rows store the Checkout Session id (cs_...).
                subscription_id = str(obj.get("id") or obj.get("subscription") or "") or None
                pi = str(obj.get("payment_intent") or "")
                if pi and paid:
                    payment = RemotePayment(
                        id=pi,
                        amount_cents=int(obj.get("amount_total") or 0),
                        currency=str(obj.get("currency") or "inr").upper()[:3],
                        status="captured",
                        method="card",
                        description=str(meta.get("plan") or "")[:255],
                    )
            elif event_type in {"invoice.paid", "invoice.payment_succeeded"}:
                subscription_id = str(obj.get("subscription") or "") or None
                pi = str(obj.get("payment_intent") or obj.get("charge") or "")
                if pi:
                    payment = RemotePayment(
                        id=pi,
                        amount_cents=int(obj.get("amount_paid") or 0),
                        currency=str(obj.get("currency") or "inr").upper()[:3],
                        status="captured",
                        method="card",
                        description=str(obj.get("description") or "")[:255],
                    )

            return WebhookEvent(
                id=event_id,
                type=event_type,
                subscription_id=subscription_id,
                payment=payment,
                order_id=order_id,
            )
        except (ValueError, TypeError, AttributeError):
            raise PaymentError("INVALID_WEBHOOK", "Malformed webhook payload.", 400) from None
