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
from backend.app.core.platform_defaults import (
    DEFAULT_AI,
    DEFAULT_CMS,
    DEFAULT_EMAIL_TEMPLATES,
    DEFAULT_NOTIFICATIONS,
    DEFAULT_PAYMENTS,
    PLATFORM_SETTINGS_KEY,
)
from backend.app.models import PlatformSettings
from backend.app.schemas.platform_settings import AiIn, AuthEmailIn, CmsIn, NotificationsIn, PaymentsIn, SmtpIn

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
        return bool(self.host and self.password)


@dataclass(frozen=True)
class EffectiveAi:
    enabled: bool
    provider: str
    base_url: str
    api_key: str
    models: dict[str, str]
    features: dict[str, bool]

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def feature_on(self, name: str) -> bool:
        return self.enabled and self.configured and bool(self.features.get(name))


@dataclass(frozen=True)
class EffectivePayments:
    provider: str
    key_id: str
    key_secret: str
    webhook_secret: str

    @property
    def configured(self) -> bool:
        return self.provider == "razorpay" and bool(self.key_id and self.key_secret)

    @property
    def active(self) -> bool:
        return self.configured

    @property
    def razorpay_mode(self) -> str:
        from backend.app.services.payments.razorpay_util import razorpay_mode_from_key_id

        return razorpay_mode_from_key_id(self.key_id)


@dataclass(frozen=True)
class EffectiveAuthEmail:
    require_verification: bool
    verification_hours: int
    password_reset_minutes: int
    frontend_url: str
    app_name: str


def get_effective_payments(db: Session | None) -> EffectivePayments:
    db_pay: dict = {}
    if db is not None:
        db_pay = _row(db).payments or {}
    key_id = str(db_pay.get("key_id") or settings.PAYMENT_KEY_ID or "").strip()
    if db_pay.get("key_secret_encrypted"):
        key_secret = decrypt_secret(db_pay.get("key_secret_encrypted") or "") or settings.PAYMENT_SECRET
    else:
        key_secret = settings.PAYMENT_SECRET
    if db_pay.get("webhook_secret_encrypted"):
        webhook = decrypt_secret(db_pay.get("webhook_secret_encrypted") or "") or settings.PAYMENT_WEBHOOK_SECRET
    else:
        webhook = settings.PAYMENT_WEBHOOK_SECRET
    provider = str(db_pay.get("provider") or settings.PAYMENT_PROVIDER or "null")
    if provider not in ("null", "razorpay"):
        provider = "null"
    if provider == "razorpay" and not (key_id and key_secret):
        provider = "null"
    return EffectivePayments(provider=provider, key_id=key_id, key_secret=key_secret, webhook_secret=webhook)


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


_LEGACY_FOOTER = "Built on the open-source Auto Job Applier (MIT)."


def get_effective_cms(db: Session) -> dict:
    row = _row(db)
    cms = _deep_merge(DEFAULT_CMS, row.cms or {})
    branding = cms.setdefault("branding", {})
    if (branding.get("footer_line") or "").strip() == _LEGACY_FOOTER:
        branding["footer_line"] = ""
    return cms


def get_public_site(db: Session) -> dict:
    cms = get_effective_cms(db)
    branding = cms.get("branding", {})
    return {
        "branding": branding,
        "banner": cms.get("banner", DEFAULT_CMS["banner"]),
        "landing": cms.get("landing", DEFAULT_CMS["landing"]),
        "legal": cms.get("legal", DEFAULT_CMS["legal"]),
    }


def get_effective_ai(db: Session | None) -> EffectiveAi:
    db_ai: dict = {}
    if db is not None:
        db_ai = _deep_merge(dict(DEFAULT_AI), _row(db).ai or {})
    enabled = bool(db_ai.get("enabled"))
    api_key = decrypt_secret(db_ai.get("api_key_encrypted") or "") if db_ai.get("api_key_encrypted") else ""
    models = _deep_merge(dict(DEFAULT_AI["models"]), db_ai.get("models") or {})
    features = _deep_merge(dict(DEFAULT_AI["features"]), db_ai.get("features") or {})
    return EffectiveAi(
        enabled=enabled,
        provider=str(db_ai.get("provider") or DEFAULT_AI["provider"]),
        base_url=str(db_ai.get("base_url") or DEFAULT_AI["base_url"]).rstrip("/"),
        api_key=api_key,
        models=models,
        features=features,
    )


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
        "email_templates": get_email_templates(db),
        "ai": _admin_ai_view(db),
        "payments": _admin_payments_view(db),
        "infrastructure": {
            "app_env": settings.APP_ENV,
            "app_version": settings.APP_VERSION,
            "database": "sqlite" if settings.is_sqlite else "postgresql",
            "redis_url_set": bool(settings.REDIS_URL),
            "cors_origins": settings.cors_origins,
            "payment_provider": get_effective_payments(db).provider,
            "payment_keys_configured": get_effective_payments(db).configured,
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


def _admin_ai_view(db: Session) -> dict:
    eff = get_effective_ai(db)
    row = _row(db)
    db_ai = row.ai or {}
    return {
        "enabled": eff.enabled,
        "provider": eff.provider,
        "base_url": eff.base_url,
        "api_key_configured": bool(db_ai.get("api_key_encrypted")),
        "models": eff.models,
        "features": eff.features,
        "ready": eff.enabled and eff.configured,
    }


def _admin_payments_view(db: Session) -> dict:
    eff = get_effective_payments(db)
    row = _row(db)
    db_pay = row.payments or {}
    mode = eff.razorpay_mode if eff.key_id else "unknown"
    return {
        "provider": eff.provider if eff.configured else str(db_pay.get("provider") or settings.PAYMENT_PROVIDER or "null"),
        "key_id": eff.key_id,
        "key_secret_configured": bool(db_pay.get("key_secret_encrypted")) or bool(settings.PAYMENT_SECRET),
        "webhook_secret_configured": bool(db_pay.get("webhook_secret_encrypted")) or bool(settings.PAYMENT_WEBHOOK_SECRET),
        "ready": eff.configured,
        "source": "database" if db_pay.get("key_id") else "environment",
        "razorpay_mode": mode,
        "live_checkout": eff.configured and mode == "live",
        "test_checkout": eff.configured and mode == "test",
    }


def update_payments(db: Session, payload: PaymentsIn) -> dict:
    row = _row(db)
    if payload.provider == "razorpay":
        kid = payload.key_id.strip() or str((row.payments or {}).get("key_id") or settings.PAYMENT_KEY_ID or "")
        if not kid:
            raise AppError("VALIDATION_ERROR", "Razorpay Key ID is required.", 422)
        from backend.app.services.payments.razorpay_util import validate_key_id

        validate_key_id(kid)
        if payload.key_secret and _fernet() is None:
            raise AppError("CONFIG_ERROR", "Set SECRET_KEY or JWT_SECRET (32+ chars) before saving payment secrets.", 503)
        if settings.APP_ENV == "production" and kid.startswith("rzp_test_"):
            raise AppError(
                "VALIDATION_ERROR",
                "Production requires live Razorpay keys (rzp_live_…). Use test keys only on staging or local.",
                422,
            )
    existing = row.payments or {}
    if payload.provider == "null" and not payload.key_id.strip():
        row.payments = {"provider": "null", "key_id": ""}
        invalidate_caches()
        return _admin_payments_view(db)
    stored: dict[str, Any] = {
        "provider": payload.provider,
        "key_id": payload.key_id.strip() or str(existing.get("key_id") or settings.PAYMENT_KEY_ID or ""),
    }
    if payload.key_secret:
        stored["key_secret_encrypted"] = encrypt_secret(payload.key_secret)
    elif existing.get("key_secret_encrypted"):
        stored["key_secret_encrypted"] = existing["key_secret_encrypted"]
    elif settings.PAYMENT_SECRET and payload.provider == "razorpay":
        pass  # env-only secret; nothing to store
    if payload.webhook_secret:
        stored["webhook_secret_encrypted"] = encrypt_secret(payload.webhook_secret)
    elif existing.get("webhook_secret_encrypted"):
        stored["webhook_secret_encrypted"] = existing["webhook_secret_encrypted"]
    row.payments = stored
    invalidate_caches()
    return _admin_payments_view(db)


def update_ai(db: Session, payload: AiIn) -> dict:
    if payload.api_key and _fernet() is None:
        raise AppError("CONFIG_ERROR", "Set SECRET_KEY or JWT_SECRET (32+ chars) before saving AI API keys.", 503)
    row = _row(db)
    existing = row.ai or {}
    stored: dict[str, Any] = {
        "enabled": payload.enabled,
        "provider": payload.provider,
        "base_url": payload.base_url.rstrip("/"),
        "models": payload.models.model_dump(),
        "features": payload.features.model_dump(),
    }
    if payload.api_key:
        stored["api_key_encrypted"] = encrypt_secret(payload.api_key)
    elif existing.get("api_key_encrypted"):
        stored["api_key_encrypted"] = existing["api_key_encrypted"]
    row.ai = stored
    invalidate_caches()
    return _admin_ai_view(db)


def _stored_email_templates(db: Session, row: PlatformSettings) -> dict:
    """Read templates from the ORM row, falling back to SQL if the mapper is behind the DB schema."""
    stored = getattr(row, "email_templates", None)
    if isinstance(stored, dict):
        return stored
    from sqlalchemy import text

    try:
        raw = db.execute(
            text("SELECT email_templates FROM platform_settings WHERE key = :k"),
            {"k": PLATFORM_SETTINGS_KEY},
        ).scalar_one_or_none()
        if isinstance(raw, dict):
            return raw
    except Exception:
        pass
    return {}


def sync_platform_defaults(db: Session) -> bool:
    """
    Add new notification types and email template keys from code defaults into the DB row.
    Existing admin edits are kept; only missing keys and fields are filled in.
    """
    row = _row(db)
    changed = False

    stored_notif = row.notifications or {}
    merged_notif = _deep_merge(dict(DEFAULT_NOTIFICATIONS), stored_notif)
    ordered_notif = {k: merged_notif[k] for k in DEFAULT_NOTIFICATIONS}
    if ordered_notif != stored_notif:
        row.notifications = ordered_notif
        changed = True

    stored_tpl = _stored_email_templates(db, row)
    merged_tpl = _deep_merge(dict(DEFAULT_EMAIL_TEMPLATES), stored_tpl)
    if merged_tpl != stored_tpl:
        if hasattr(type(row), "email_templates"):
            row.email_templates = merged_tpl
        else:
            from sqlalchemy import text
            import json

            db.execute(
                text("UPDATE platform_settings SET email_templates = :payload WHERE key = :k"),
                {"k": PLATFORM_SETTINGS_KEY, "payload": json.dumps(merged_tpl)},
            )
        changed = True

    if changed:
        invalidate_caches()
    return changed


def get_email_templates(db: Session) -> dict:
    row = _row(db)
    return _deep_merge(dict(DEFAULT_EMAIL_TEMPLATES), _stored_email_templates(db, row))


def update_email_templates(db: Session, payload: EmailTemplatesIn) -> dict:
    auth_keys = set((DEFAULT_EMAIL_TEMPLATES.get("auth") or {}).keys())
    event_keys = set((DEFAULT_EMAIL_TEMPLATES.get("events") or {}).keys())
    if set(payload.auth.keys()) != auth_keys:
        raise AppError("VALIDATION_ERROR", "Auth templates must include every known template key.", 422)
    if set(payload.events.keys()) != event_keys:
        raise AppError("VALIDATION_ERROR", "Event templates must include every known notification type.", 422)
    row = _row(db)
    payload_dict = {
        "auth": {k: v.model_dump() for k, v in payload.auth.items()},
        "events": {k: v.model_dump() for k, v in payload.events.items()},
    }
    if hasattr(type(row), "email_templates"):
        row.email_templates = payload_dict
    else:
        from sqlalchemy import text

        import json

        db.execute(
            text("UPDATE platform_settings SET email_templates = :payload WHERE key = :k"),
            {"k": PLATFORM_SETTINGS_KEY, "payload": json.dumps(payload_dict)},
        )
    invalidate_caches()
    return get_email_templates(db)


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
