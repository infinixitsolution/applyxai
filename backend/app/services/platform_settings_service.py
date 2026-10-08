"""Load and update platform settings (DB overrides with .env fallback)."""

from __future__ import annotations

import base64
import hashlib
import logging
from dataclasses import dataclass
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.errors import AppError
from backend.app.core.platform_defaults import DEFAULT_CMS, DEFAULT_NOTIFICATIONS, PLATFORM_SETTINGS_KEY
from backend.app.models import PlatformSettings
from backend.app.schemas.platform_settings import AuthEmailIn, CmsIn, NotificationsIn, SmtpIn

logger = logging.getLogger("applyxai.settings")

SMTPS_PORT = 465


def _fernet() -> Fernet | None:
    secret = settings.SECRET_KEY or settings.JWT_SECRET
    if len(secret) < 32:
        return None
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    f = _fernet()
    if f is None:
        raise AppError("CONFIG_ERROR", "SECRET_KEY or JWT_SECRET (32+ chars) is required to store SMTP passwords.", 503)
    return f.encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    f = _fernet()
    if f is None:
        return ""
    try:
        return f.decrypt(value.encode()).decode()
    except InvalidToken:
        logger.warning("Could not decrypt stored SMTP password")
        return ""


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        elif value is not None and value != "":
            out[key] = value
    return out


def _row(db: Session) -> PlatformSettings:
    row = db.get(PlatformSettings, PLATFORM_SETTINGS_KEY)
    if row is None:
        row = PlatformSettings(key=PLATFORM_SETTINGS_KEY)
        db.add(row)
        db.flush()
    return row


@dataclass(frozen=True)
class EffectiveSmtp:
    host: str
    port: int
    username: str
    password: str
    from_address: str

    @property
    def configured(self) -> bool:
        return bool(self.host)


@dataclass(frozen=True)
class EffectiveAuthEmail:
    require_verification: bool
    verification_hours: int
    password_reset_minutes: int
    frontend_url: str
    app_name: str


def get_effective_smtp(db: Session | None) -> EffectiveSmtp:
    db_smtp: dict = {}
    if db is not None:
        db_smtp = _row(db).smtp or {}
    use_db = db_smtp.get("enabled", True) and bool(db_smtp.get("host"))
    if use_db:
        password = decrypt_secret(db_smtp.get("password_encrypted") or "")
        return EffectiveSmtp(
            host=str(db_smtp.get("host") or ""),
            port=int(db_smtp.get("port") or 587),
            username=str(db_smtp.get("username") or ""),
            password=password,
            from_address=str(db_smtp.get("from_address") or settings.SMTP_FROM),
        )
    return EffectiveSmtp(
        host=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USERNAME,
        password=settings.SMTP_PASSWORD,
        from_address=settings.SMTP_FROM,
    )


def get_effective_auth(db: Session | None) -> EffectiveAuthEmail:
    auth: dict = {}
    cms = DEFAULT_CMS
    if db is not None:
        row = _row(db)
        auth = row.auth_email or {}
        cms = _deep_merge(DEFAULT_CMS, row.cms or {})
    app_name = cms.get("branding", {}).get("app_name") or settings.APP_NAME
    return EffectiveAuthEmail(
        require_verification=auth["require_verification"] if "require_verification" in auth else settings.REQUIRE_EMAIL_VERIFICATION,
        verification_hours=int(auth["verification_hours"]) if "verification_hours" in auth else settings.EMAIL_VERIFICATION_HOURS,
        password_reset_minutes=int(auth["password_reset_minutes"])
        if "password_reset_minutes" in auth
        else settings.PASSWORD_RESET_MINUTES,
        frontend_url=str(auth["frontend_url"]) if auth.get("frontend_url") else settings.FRONTEND_URL,
        app_name=app_name,
    )


def get_effective_cms(db: Session) -> dict:
    row = _row(db)
    return _deep_merge(DEFAULT_CMS, row.cms or {})


def get_public_site(db: Session) -> dict:
    cms = get_effective_cms(db)
    branding = cms.get("branding", {})
    return {
        "branding": branding,
        "banner": cms.get("banner", DEFAULT_CMS["banner"]),
        "landing": cms.get("landing", DEFAULT_CMS["landing"]),
        "legal": cms.get("legal", DEFAULT_CMS["legal"]),
    }


def get_notification_prefs(db: Session) -> dict[str, dict]:
    row = _row(db)
    merged = _deep_merge(DEFAULT_NOTIFICATIONS, row.notifications or {})
    return merged


def notification_email_enabled(db: Session, event_type: str) -> bool:
    prefs = get_notification_prefs(db)
    entry = prefs.get(event_type) or {}
    return bool(entry.get("email"))


def invalidate_caches() -> None:
    pass


def build_admin_view(db: Session) -> dict:
    smtp_eff = get_effective_smtp(db)
    auth_eff = get_effective_auth(db)
    row = _row(db)
    db_smtp = row.smtp or {}
    return {
        "cms": get_effective_cms(db),
        "smtp": {
            "enabled": bool(db_smtp.get("host")) and db_smtp.get("enabled", True),
            "host": smtp_eff.host,
            "port": smtp_eff.port,
            "security": "ssl" if smtp_eff.port == SMTPS_PORT else "starttls",
            "username": smtp_eff.username,
            "from_address": smtp_eff.from_address,
            "password_configured": bool(db_smtp.get("password_encrypted")) or bool(settings.SMTP_PASSWORD),
            "mode": "smtp" if smtp_eff.configured else "console",
            "source": "database" if db_smtp.get("host") else "environment",
        },
        "auth_email": {
            "require_verification": auth_eff.require_verification,
            "verification_hours": auth_eff.verification_hours,
            "password_reset_minutes": auth_eff.password_reset_minutes,
            "frontend_url": auth_eff.frontend_url,
        },
        "notifications": get_notification_prefs(db),
        "infrastructure": {
            "app_env": settings.APP_ENV,
            "app_version": settings.APP_VERSION,
            "database": "sqlite" if settings.is_sqlite else "postgresql",
            "redis_url_set": bool(settings.REDIS_URL),
            "cors_origins": settings.cors_origins,
            "payment_provider": settings.PAYMENT_PROVIDER,
            "payment_keys_configured": bool(settings.PAYMENT_KEY_ID and settings.PAYMENT_SECRET),
        },
    }


def update_cms(db: Session, payload: CmsIn) -> dict:
    row = _row(db)
    row.cms = payload.model_dump()
    invalidate_caches()
    return get_effective_cms(db)


def update_smtp(db: Session, payload: SmtpIn) -> dict:
    if payload.password and settings.APP_ENV == "production" and _fernet() is None:
        raise AppError("CONFIG_ERROR", "Set SECRET_KEY or JWT_SECRET (32+ chars) before saving SMTP passwords.", 503)
    row = _row(db)
    if not payload.host.strip():
        row.smtp = {}
        invalidate_caches()
        return build_admin_view(db)["smtp"]
    existing = row.smtp or {}
    stored: dict[str, Any] = {
        "enabled": payload.enabled,
        "host": payload.host.strip(),
        "port": payload.port,
        "username": payload.username.strip(),
        "from_address": payload.from_address.strip(),
    }
    if payload.password:
        stored["password_encrypted"] = encrypt_secret(payload.password)
    elif existing.get("password_encrypted"):
        stored["password_encrypted"] = existing["password_encrypted"]
    row.smtp = stored
    invalidate_caches()
    return build_admin_view(db)["smtp"]


def update_auth_email(db: Session, payload: AuthEmailIn) -> dict:
    row = _row(db)
    row.auth_email = payload.model_dump()
    invalidate_caches()
    return build_admin_view(db)["auth_email"]


def update_notifications(db: Session, payload: NotificationsIn) -> dict:
    row = _row(db)
    base = _deep_merge(DEFAULT_NOTIFICATIONS, row.notifications or {})
    for key, value in payload.types.items():
        if key not in DEFAULT_NOTIFICATIONS:
            raise AppError("VALIDATION_ERROR", f"Unknown notification type: {key}", 422)
        base[key] = {**base[key], "email": value.email}
    row.notifications = {k: base[k] for k in DEFAULT_NOTIFICATIONS}
    invalidate_caches()
    return get_notification_prefs(db)
