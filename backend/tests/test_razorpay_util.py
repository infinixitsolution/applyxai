import pytest

from backend.app.core.errors import AppError
from backend.app.services.payments.razorpay_util import razorpay_mode_from_key_id, validate_key_id


def test_mode_from_key_id():
    assert razorpay_mode_from_key_id("rzp_test_abc") == "test"
    assert razorpay_mode_from_key_id("rzp_live_xyz") == "live"
    assert razorpay_mode_from_key_id("bad") == "unknown"


def test_validate_key_id():
    validate_key_id("rzp_test_123")
    with pytest.raises(AppError) as err:
        validate_key_id("sk_live_foo")
    assert err.value.code == "VALIDATION_ERROR"
