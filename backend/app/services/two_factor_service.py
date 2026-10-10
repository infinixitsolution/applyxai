"""TOTP two-factor authentication (RFC 6238) for user accounts."""

from __future__ import annotations

from urllib.parse import quote

import pyotp
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.models import User
from backend.app.services.platform_settings_service import decrypt_secret, encrypt_secret


def _invalid_code() -> AppError:
    return AppError("INVALID_TOTP", "That authenticator code didn't match. Try again.", 401)


def totp_enabled(user: User) -> bool:
    return bool(user.totp_enabled and user.totp_secret_encrypted)


def _load_secret(user: User) -> str:
    raw = decrypt_secret(user.totp_secret_encrypted or "")
    if not raw:
        raise AppError("TOTP_NOT_CONFIGURED", "Two-factor authentication isn't set up.", 400)
    return raw


def _verify(user: User, code: str) -> None:
    secret = _load_secret(user)
    totp = pyotp.TOTP(secret)
    normalized = (code or "").strip().replace(" ", "")
    if not normalized.isdigit() or len(normalized) != 6:
        raise _invalid_code()
    if not totp.verify(normalized, valid_window=1):
        raise _invalid_code()


def begin_setup(user: User) -> dict:
    secret = pyotp.random_base32()
    user.totp_secret_encrypted = encrypt_secret(secret)
    user.totp_enabled = False
    label = quote(f"{user.email}")
    issuer = "ApplyXAI"
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=label, issuer_name=issuer)
    return {"secret": secret, "otpauth_uri": uri}


def confirm_setup(db: Session, user: User, code: str) -> None:
    if not user.totp_secret_encrypted:
        raise AppError("TOTP_NOT_CONFIGURED", "Start setup before entering a code.", 400)
    _verify(user, code)
    user.totp_enabled = True
    db.flush()


def disable(db: Session, user: User, password: str, code: str) -> None:
    from backend.app.core.security import verify_password

    if not verify_password(password, user.password_hash):
        raise AppError("INVALID_CREDENTIALS", "Incorrect password.", 401)
    if not totp_enabled(user):
        raise AppError("TOTP_NOT_ENABLED", "Two-factor authentication is already off.", 400)
    _verify(user, code)
    user.totp_enabled = False
    user.totp_secret_encrypted = ""
    db.flush()


def verify_login_code(user: User, code: str) -> None:
    if not totp_enabled(user):
        return
    _verify(user, code)
