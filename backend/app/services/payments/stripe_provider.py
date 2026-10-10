"""
Stripe billing provider (Checkout + webhooks).

Admin stores the secret key in the same encrypted fields as Razorpay (`key_id` = publishable key,
`key_secret` = secret key, `webhook_secret` = Stripe signing secret). Full Checkout session flow
is planned; until then configured Stripe mode returns a clear error instead of silently using NullProvider.
"""

from backend.app.models import Plan, User
from backend.app.services.payments.base import (
    CheckoutConfirmation, PaymentError, RemotePayment, RemoteSubscription, WebhookEvent,
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

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> WebhookEvent:
        raise _NOT_READY
