"""Razorpay key environment (test vs live) — derived from Key ID prefix."""

from __future__ import annotations

from typing import Literal

RazorpayMode = Literal["test", "live", "unknown"]

TEST_CHECKOUT_HINT = (
    "Test mode: use card 4111 1111 1111 1111 (any future expiry, any CVV) or UPI success@razorpay in Checkout. "
    "No real money is charged with test keys."
)


def razorpay_mode_from_key_id(key_id: str) -> RazorpayMode:
    kid = (key_id or "").strip()
    if kid.startswith("rzp_live_"):
        return "live"
    if kid.startswith("rzp_test_"):
        return "test"
    return "unknown"


def validate_key_id(key_id: str) -> None:
    from backend.app.core.errors import AppError

    if razorpay_mode_from_key_id(key_id) == "unknown":
        raise AppError(
            "VALIDATION_ERROR",
            "Key ID must start with rzp_test_ (sandbox) or rzp_live_ (production).",
            422,
        )
