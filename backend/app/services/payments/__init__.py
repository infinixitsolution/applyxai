from fastapi import Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.services.payments.base import PaymentError, PaymentProvider
from backend.app.services.platform_settings_service import get_effective_payments


def resolve_payment_provider(db: Session | None) -> PaymentProvider:
    """Active provider from admin payment settings (DB) with .env fallback."""
    eff = get_effective_payments(db)
    if eff.provider == "razorpay" and eff.configured:
        from backend.app.services.payments.razorpay import RazorpayProvider
        return RazorpayProvider(eff.key_id, eff.key_secret, eff.webhook_secret)
    from backend.app.services.payments.null import NullProvider
    return NullProvider()


def get_payment_provider(db: Session = Depends(get_db)) -> PaymentProvider:
    """FastAPI dependency (overridden in tests)."""
    return resolve_payment_provider(db)


__all__ = ["PaymentError", "PaymentProvider", "get_payment_provider", "resolve_payment_provider"]
