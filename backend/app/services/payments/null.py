"""
Development-only provider: a checkout grants the plan at once, with no payment. The settings
refuse PAYMENT_PROVIDER=null when APP_ENV=production.
"""

import secrets
from datetime import datetime, timezone

from backend.app.models import Plan, SubscriptionStatus, User
from backend.app.services.payments.base import (
    CheckoutConfirmation, PaymentError, RemotePayment, RemoteSubscription, WebhookEvent,
)

_NO_PAYMENTS = PaymentError("NOT_SUPPORTED", "Online payments aren't enabled on this server.", 404)


def _add_month(dt: datetime) -> datetime:
    year, month = dt.year + dt.month // 12, dt.month % 12 + 1
    day = min(dt.day, 28)
    return dt.replace(year=year, month=month, day=day)


class NullProvider:
    name = "null"

    def create_plan(self, plan: Plan) -> str:
        return ""

    def create_subscription(self, plan: Plan, user: User) -> RemoteSubscription:
        now = datetime.now(timezone.utc)
        return RemoteSubscription(id=f"null_sub_{secrets.token_hex(8)}", status=SubscriptionStatus.ACTIVE,
                                  raw_status="active", current_start=now, current_end=_add_month(now))

    def fetch_subscription(self, subscription_id: str) -> RemoteSubscription:
        return RemoteSubscription(id=subscription_id, status=SubscriptionStatus.ACTIVE, raw_status="active")

    def cancel_subscription(self, subscription_id: str, *, at_period_end: bool) -> RemoteSubscription:
        status = SubscriptionStatus.ACTIVE if at_period_end else SubscriptionStatus.CANCELLED
        return RemoteSubscription(id=subscription_id, status=status, raw_status=status.value)

    def fetch_payment(self, payment_id: str) -> RemotePayment:
        raise _NO_PAYMENTS

    def checkout_options(self, subscription_id: str, plan: Plan, user: User) -> None:
        return None

    def verify_checkout(self, payment_id: str, subscription_id: str, signature: str) -> CheckoutConfirmation:
        raise _NO_PAYMENTS

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> WebhookEvent:
        raise _NO_PAYMENTS
