"""Password hashing, access tokens (JWT), and opaque one-time tokens."""

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from backend.app.core.config import settings

logger = logging.getLogger("applyxai.security")

_hasher = PasswordHasher()  # Argon2id with argon2-cffi's current recommended parameters
_JWT_ALGORITHM = "HS256"
_JWT_AUDIENCE = "applyxai-api"


# --------------------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


@lru_cache
def _dummy_hash() -> str:
    return _hasher.hash(secrets.token_urlsafe(16))


def burn_password_check(password: str) -> None:
    """Spend the same time as a real verification, so unknown emails can't be timed apart."""
    verify_password(password, _dummy_hash())


# --------------------------------------------------------------------------- opaque tokens
def generate_token() -> str:
    """256-bit URL-safe token for emails and refresh cookies. Only its hash is stored."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    # High-entropy random input, so a fast hash is appropriate (no salt/stretching needed).
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- access tokens
@lru_cache
def _jwt_secret() -> str:
    if settings.JWT_SECRET:
        return settings.JWT_SECRET
    # Production refuses to start without JWT_SECRET (see config.py). In development a
    # per-process secret is fine: sessions simply end when the server restarts.
    logger.warning("JWT_SECRET is not set; using a temporary secret. Sessions end on restart.")
    return secrets.token_urlsafe(48)


def create_access_token(user_id: uuid.UUID, token_version: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "ver": token_version,
        "type": "access",
        "aud": _JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Claims of a valid, unexpired access token, or None."""
    try:
        claims = jwt.decode(
            token, _jwt_secret(), algorithms=[_JWT_ALGORITHM], audience=_JWT_AUDIENCE,
            options={"require": ["sub", "exp", "iat", "type", "ver"]},
        )
    except jwt.PyJWTError:
        return None
    return claims if claims.get("type") == "access" else None
