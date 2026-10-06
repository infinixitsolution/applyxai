from functools import lru_cache

from backend.app.core.config import settings
from backend.app.services.payments.base import PaymentError, PaymentProvider


@lru_cache
def _razorpay():
    from backend.app.services.payments.razorpay import RazorpayProvider
    return RazorpayProvider(settings.PAYMENT_KEY_ID, settings.PAYMENT_SECRET, settings.PAYMENT_WEBHOOK_SECRET)


def get_payment_provider() -> PaymentProvider:
    """FastAPI dependency (overridden in tests): the provider selected by PAYMENT_PROVIDER."""
    if settings.PAYMENT_PROVIDER == "razorpay":
        return _razorpay()
    from backend.app.services.payments.null import NullProvider
    return NullProvider()


__all__ = ["PaymentError", "PaymentProvider", "get_payment_provider"]
