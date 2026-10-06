"""
Registration, login sessions, email verification, and password reset.

Sessions: a short-lived JWT access token plus an opaque refresh token (stored hashed).
Refresh tokens rotate on every use; presenting an already-used one means it was stolen,
so every session of that user is revoked.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.errors import AppError
from backend.app.core.security import (
    burn_password_check, create_access_token, generate_token, hash_password, hash_token,
    password_needs_rehash, verify_password,
)
from backend.app.models import AuthToken, TokenPurpose, User

logger = logging.getLogger("applyxai.auth")

def INVALID_CREDENTIALS() -> AppError:
    return AppError("INVALID_CREDENTIALS", "Incorrect email or password.", 401)


def INVALID_TOKEN() -> AppError:
    return AppError("INVALID_TOKEN", "This link is invalid or has expired.", 400)


def SESSION_EXPIRED() -> AppError:
    return AppError("SESSION_EXPIRED", "Your session has expired. Please log in again.", 401)


REFRESH_RACE_GRACE = timedelta(seconds=10)


@dataclass
class SessionTokens:
    user: User
    access_token: str
    refresh_token: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    # SQLite returns naive datetimes even for timezone-aware columns; they are stored as UTC.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def normalize_email(email: str) -> str:
    return email.strip().lower()


# --------------------------------------------------------------------------- tokens
def _issue_token(db: Session, user: User, purpose: TokenPurpose, lifetime: timedelta) -> str:
    raw = generate_token()
    db.add(AuthToken(user_id=user.id, purpose=purpose, token_hash=hash_token(raw), expires_at=_now() + lifetime))
    return raw


def _invalidate_tokens(db: Session, user_id, purpose: TokenPurpose) -> None:
    db.execute(
        update(AuthToken)
        .where(AuthToken.user_id == user_id, AuthToken.purpose == purpose, AuthToken.used_at.is_(None))
        .values(used_at=_now())
    )


def _find_token(db: Session, raw: str, purpose: TokenPurpose) -> AuthToken | None:
    return db.scalar(select(AuthToken).where(AuthToken.token_hash == hash_token(raw), AuthToken.purpose == purpose))


def _consume_email_token(db: Session, raw: str, purpose: TokenPurpose) -> User:
    token = _find_token(db, raw, purpose)
    if token is None or token.used_at is not None or _aware(token.expires_at) <= _now():
        raise INVALID_TOKEN()
    token.used_at = _now()
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise INVALID_TOKEN()
    return user


# --------------------------------------------------------------------------- registration
def register(db: Session, email: str, password: str, first_name: str, last_name: str) -> tuple[User | None, str | None]:
    """
    Returns (new_user, verification_token), or (None, None) when the email is already
    registered. The API answers both cases identically so it can't be used to discover
    which emails have accounts; the existing owner gets a heads-up email instead.
    """
    email = normalize_email(email)
    if password.lower() == email:
        raise AppError("WEAK_PASSWORD", "Password must not be your email address.", 422)
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        return None, None

    user = User(email=email, password_hash=hash_password(password), first_name=first_name, last_name=last_name,
                is_verified=not settings.REQUIRE_EMAIL_VERIFICATION)
    db.add(user)
    db.flush()
    token = None
    if settings.REQUIRE_EMAIL_VERIFICATION:
        token = _issue_token(db, user, TokenPurpose.VERIFY_EMAIL, timedelta(hours=settings.EMAIL_VERIFICATION_HOURS))
    db.commit()
    logger.info("user registered", extra={"user_id": str(user.id), "event": "user_registered"})
    return user, token


def verify_email(db: Session, raw_token: str) -> User:
    user = _consume_email_token(db, raw_token, TokenPurpose.VERIFY_EMAIL)
    user.is_verified = True
    _invalidate_tokens(db, user.id, TokenPurpose.VERIFY_EMAIL)
    db.commit()
    return user


def new_verification_token(db: Session, email: str) -> tuple[User | None, str | None]:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or user.is_verified or not user.is_active:
        return None, None
    _invalidate_tokens(db, user.id, TokenPurpose.VERIFY_EMAIL)
    token = _issue_token(db, user, TokenPurpose.VERIFY_EMAIL, timedelta(hours=settings.EMAIL_VERIFICATION_HOURS))
    db.commit()
    return user, token


# --------------------------------------------------------------------------- sessions
def _start_session(db: Session, user: User) -> SessionTokens:
    refresh = _issue_token(db, user, TokenPurpose.REFRESH, timedelta(days=settings.REFRESH_TOKEN_DAYS))
    return SessionTokens(user, create_access_token(user.id, user.token_version), refresh)


def login(db: Session, email: str, password: str) -> SessionTokens:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        burn_password_check(password)
        raise INVALID_CREDENTIALS()
    if not verify_password(password, user.password_hash):
        raise INVALID_CREDENTIALS()
    # Only reachable with the correct password, so these don't reveal anything to a guesser.
    if not user.is_active:
        raise AppError("ACCOUNT_DISABLED", "This account has been disabled.", 403)
    if settings.REQUIRE_EMAIL_VERIFICATION and not user.is_verified:
        raise AppError("EMAIL_NOT_VERIFIED", "Please verify your email address before logging in.", 403)

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = _now()
    session = _start_session(db, user)
    db.commit()
    logger.info("login", extra={"user_id": str(user.id), "event": "login"})
    return session


def refresh(db: Session, raw_refresh: str) -> SessionTokens:
    token = _find_token(db, raw_refresh, TokenPurpose.REFRESH)
    if token is None:
        raise SESSION_EXPIRED()
    if token.used_at is not None:
        if _now() - _aware(token.used_at) < REFRESH_RACE_GRACE:
            # Two tabs refreshed at once; the browser already holds the winner's new cookie.
            raise SESSION_EXPIRED()
        logger.warning("refresh token reuse; revoking all sessions",
                       extra={"user_id": str(token.user_id), "event": "refresh_token_reuse"})
        revoke_all_sessions(db, token.user_id)
        db.commit()
        raise SESSION_EXPIRED()
    user = db.get(User, token.user_id)
    if _aware(token.expires_at) <= _now() or user is None or not user.is_active:
        raise SESSION_EXPIRED()
    token.used_at = _now()
    session = _start_session(db, user)
    db.commit()
    return session


def logout(db: Session, raw_refresh: str | None) -> None:
    if not raw_refresh:
        return
    token = _find_token(db, raw_refresh, TokenPurpose.REFRESH)
    if token is not None and token.used_at is None:
        token.used_at = _now()
        db.commit()


def revoke_all_sessions(db: Session, user_id) -> None:
    """End every session: refresh tokens die now, access tokens fail their version check."""
    _invalidate_tokens(db, user_id, TokenPurpose.REFRESH)
    db.execute(update(User).where(User.id == user_id).values(token_version=User.token_version + 1))


# --------------------------------------------------------------------------- password reset
def new_password_reset_token(db: Session, email: str) -> tuple[User | None, str | None]:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or not user.is_active:
        return None, None
    _invalidate_tokens(db, user.id, TokenPurpose.RESET_PASSWORD)
    token = _issue_token(db, user, TokenPurpose.RESET_PASSWORD, timedelta(minutes=settings.PASSWORD_RESET_MINUTES))
    db.commit()
    return user, token


def reset_password(db: Session, raw_token: str, new_password: str) -> None:
    user = _consume_email_token(db, raw_token, TokenPurpose.RESET_PASSWORD)
    if new_password.lower() == user.email:
        raise AppError("WEAK_PASSWORD", "Password must not be your email address.", 422)
    user.password_hash = hash_password(new_password)
    # Receiving the reset link proves control of the inbox.
    user.is_verified = True
    _invalidate_tokens(db, user.id, TokenPurpose.RESET_PASSWORD)
    revoke_all_sessions(db, user.id)
    db.commit()
    logger.info("password reset", extra={"user_id": str(user.id), "event": "password_reset"})
