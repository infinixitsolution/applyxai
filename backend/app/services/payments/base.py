"""
The payment-provider contract. Billing code talks only to this interface, so Razorpay can be
joined or replaced by another provider without touching subscriptions or the API.

Nothing a browser sends is trusted on its own: a checkout confirmation is checked against
the provider's signature and then re-read from the provider's API, and webhooks are
signature-checked before anything in them is used.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from backend.app.core.errors import AppError
from backend.app.models import Plan, SubscriptionStatus, User


class PaymentError(AppError):
    """A provider call failed or a signature didn't match. The message is safe to show to users."""


@dataclass
class RemoteSubscription:
    """A subscription as the provider reports it. None means "unknown; keep what we have"."""

    id: str
    status: SubscriptionStatus
    raw_status: str = ""
    plan_id: str = ""
    customer_id: str = ""
    current_start: datetime | None = None
    current_end: datetime | None = None
    notes: dict = field(default_factory=dict)


@dataclass
class RemotePayment:
    id: str
    amount_cents: int
    currency: str
    status: str
    method: str = ""
    description: str = ""
    created_at: datetime | None = None


@dataclass
class WebhookEvent:
    id: str
    type: str
    subscription_id: str | None = None
    payment: RemotePayment | None = None


@dataclass
class CheckoutConfirmation:
    subscription_id: str
    payment_id: str


class PaymentProvider(Protocol):
    name: str

    def create_plan(self, plan: Plan) -> str:
        """Create the plan at the provider; returns its ID for `plans.provider_plan_id`."""

    def create_subscription(self, plan: Plan, user: User) -> RemoteSubscription: ...

    def fetch_subscription(self, subscription_id: str) -> RemoteSubscription: ...

    def cancel_subscription(self, subscription_id: str, *, at_period_end: bool) -> RemoteSubscription: ...

    def fetch_payment(self, payment_id: str) -> RemotePayment: ...

    def checkout_options(self, subscription_id: str, plan: Plan, user: User) -> dict | None:
        """What the browser needs to open the provider's checkout; None when no checkout is needed."""

    def verify_checkout(self, payment_id: str, subscription_id: str, signature: str) -> CheckoutConfirmation:
        """Check the signature the provider's checkout returned. Raises PaymentError."""

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> WebhookEvent:
        """Verify the signature, then parse. Raises PaymentError."""
