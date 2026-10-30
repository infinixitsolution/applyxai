"""Load and update platform settings (DB overrides with .env fallback)."""

from __future__ import annotations

import base64
import hashlib
import logging
import time
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
    DEFAULT_JOB_SOURCES,
    DEFAULT_LIVE_INTERVIEW,
    DEFAULT_NOTIFICATIONS,
    DEFAULT_OUTREACH_CAMPAIGN,
    DEFAULT_PAYMENTS,
    PLATFORM_SETTINGS_KEY,
)
from backend.app.models import PlatformSettings
from backend.app.schemas.platform_settings import (
    AiIn, AuthEmailIn, CmsIn, GstSettingsIn, JobSourcesIn, LiveInterviewSettingsIn, NotificationsIn,
    OutreachSettingsIn, PaymentsIn, SmtpIn,
)

logger = logging.getLogger("applyxai.settings")

SMTPS_PORT = 465
_PLATFORM_ROW_CACHE: tuple[float, Any] | None = None
_PLATFORM_ROW_TTL_SEC = 3.0


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
    global _PLATFORM_ROW_CACHE
    now = time.monotonic()
    if _PLATFORM_ROW_CACHE is not None:
        cached_at, cached_row = _PLATFORM_ROW_CACHE
        # A row loaded by another request's session can't be saved through this one; edits to it would be lost.
        if now - cached_at < _PLATFORM_ROW_TTL_SEC and cached_row in db:
            return cached_row
    row = db.get(PlatformSettings, PLATFORM_SETTINGS_KEY)
    if row is None:
        row = PlatformSettings(key=PLATFORM_SETTINGS_KEY)
        db.add(row)
        db.flush()
    _PLATFORM_ROW_CACHE = (now, row)
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
        if not (self.enabled and self.configured):
            return False
        if name == "outreach":
            # Legacy rows saved before outreach existed: follow Application Q&A toggle.
            if "outreach" not in self.features:
                return bool(self.features.get("applications", True))
        return bool(self.features.get(name))


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
    if provider not in ("null", "razorpay", "stripe"):
        provider = "null"
    if provider in ("razorpay", "stripe") and not (key_id and key_secret):
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


def _normalize_cms_seo(cms: dict) -> None:
    seo = cms.setdefault("seo", {})
    defaults = DEFAULT_CMS.get("seo") or {}
    merged = _deep_merge(dict(defaults), seo if isinstance(seo, dict) else {})
    default_pages = (defaults.get("pages") or {})
    pages = merged.get("pages") if isinstance(merged.get("pages"), dict) else {}
    merged["pages"] = _deep_merge(dict(default_pages), pages)
    cms["seo"] = merged


def get_effective_cms(db: Session) -> dict:
    row = _row(db)
    cms = _deep_merge(DEFAULT_CMS, row.cms or {})
    branding = cms.setdefault("branding", {})
    if (branding.get("footer_line") or "").strip() == _LEGACY_FOOTER:
        branding["footer_line"] = ""
    _normalize_cms_seo(cms)
    return cms


def get_public_site(db: Session) -> dict:
    cms = get_effective_cms(db)
    branding = cms.get("branding", {})
    return {
        "branding": branding,
        "banner": cms.get("banner", DEFAULT_CMS["banner"]),
        "landing": cms.get("landing", DEFAULT_CMS["landing"]),
        "legal": cms.get("legal", DEFAULT_CMS["legal"]),
        "seo": cms.get("seo", DEFAULT_CMS["seo"]),
    }


def get_effective_ai(db: Session | None) -> EffectiveAi:
    db_ai: dict = {}
    if db is not None:
        db_ai = _deep_merge(dict(DEFAULT_AI), _row(db).ai or {})
    enabled = bool(db_ai.get("enabled"))
    encrypted = db_ai.get("api_key_encrypted") or ""
    api_key = decrypt_secret(encrypted) if encrypted else ""
    if encrypted and not api_key:
        logger.warning("Platform AI API key is stored but could not be decrypted (check SECRET_KEY/JWT_SECRET)")
    models = _deep_merge(dict(DEFAULT_AI["models"]), db_ai.get("models") or {})
    raw_features = db_ai.get("features")
    if not isinstance(raw_features, dict):
        raw_features = {}
    features = _deep_merge(dict(DEFAULT_AI["features"]), raw_features)
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
    """Clear the short-lived in-process platform settings row cache after admin updates."""
    global _PLATFORM_ROW_CACHE
    _PLATFORM_ROW_CACHE = None


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
        "live_interview": get_live_interview(db),
        "job_sources": get_job_sources(db),
        "outreach": get_outreach_admin(db),
        "gst": get_gst_admin(db),
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


def _merge_mock_interview_voice_admin(db_ai: dict) -> dict:
    from backend.app.core.platform_defaults import DEFAULT_AI

    base = dict(DEFAULT_AI.get("mock_interview_voice") or {})
    raw = db_ai.get("mock_interview_voice")
    if isinstance(raw, dict):
        for key in ("provider", "elevenlabs_agent_id", "elevenlabs_model_id", "elevenlabs_voice_id"):
            if raw.get(key) not in (None, ""):
                base[key] = raw[key]
    return {
        "provider": str(base.get("provider") or "elevenlabs"),
        "elevenlabs_agent_id": str(base.get("elevenlabs_agent_id") or "fA4eSDsx5xNZ1RV7zEu5"),
        "elevenlabs_model_id": str(base.get("elevenlabs_model_id") or "eleven_multilingual_v2"),
    }


def list_mock_interviews_unlimited_emails(db: Session) -> list[str]:
    row = _row(db)
    ai = row.ai if isinstance(getattr(row, "ai", None), dict) else {}
    raw = ai.get("mock_interviews_unlimited_emails")
    if not isinstance(raw, list):
        return []
    return sorted({str(item).strip().lower() for item in raw if str(item).strip()})


def add_mock_interviews_unlimited_email(db: Session, email: str) -> list[str]:
    normalized = email.strip().lower()
    if not normalized:
        raise AppError("VALIDATION_ERROR", "Email is required.", 422)
    row = _row(db)
    current = list_mock_interviews_unlimited_emails(db)
    if normalized not in current:
        current.append(normalized)
        current.sort()
    row.ai = {**(row.ai or {}), "mock_interviews_unlimited_emails": current}
    invalidate_caches()
    return current


def _admin_ai_view(db: Session) -> dict:
    eff = get_effective_ai(db)
    row = _row(db)
    db_ai = row.ai or {}
    from backend.app.core.config import settings
    from backend.app.core.platform_defaults import merge_mock_interview_presenter

    presenter = merge_mock_interview_presenter(db_ai.get("mock_interview_presenter"))
    elevenlabs_db = bool(db_ai.get("elevenlabs_api_key_encrypted"))
    env_eleven = (settings.ELEVENLABS_API_KEY or "").strip()
    return {
        "enabled": eff.enabled,
        "provider": eff.provider,
        "base_url": eff.base_url,
        "api_key_configured": bool(db_ai.get("api_key_encrypted")),
        "elevenlabs_api_key_configured": elevenlabs_db or bool(env_eleven),
        "elevenlabs_api_key_source": "database" if elevenlabs_db else ("environment" if env_eleven else "none"),
        "models": eff.models,
        "features": eff.features,
        "ready": eff.enabled and eff.configured,
        "resume_ready": eff.feature_on("resume"),
        "mock_interview_ready": eff.feature_on("mock_interview"),
        "outreach_ready": eff.feature_on("outreach"),
        "mock_interview_presenter": presenter,
        "mock_interview_voice": _merge_mock_interview_voice_admin(db_ai),
        "mock_interviews_unlimited_emails": list_mock_interviews_unlimited_emails(db),
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


def get_job_sources(db: Session) -> dict:
    from backend.app.core.config import get_settings

    row = _row(db)
    stored = row.job_sources if isinstance(getattr(row, "job_sources", None), dict) else {}
    merged = {**DEFAULT_JOB_SOURCES, **stored}
    if get_settings().ENABLE_NAUKRI:
        merged["naukri"] = True
    return {"linkedin": bool(merged.get("linkedin")), "naukri": bool(merged.get("naukri"))}


def enabled_source_names(db: Session) -> list[str]:
    flags = get_job_sources(db)
    return [name for name in ("linkedin", "naukri") if flags[name]]


def update_job_sources(db: Session, payload: JobSourcesIn) -> dict:
    names = payload.enabled_names()
    if not names:
        raise AppError("VALIDATION_ERROR", "Turn on at least one job source.", 422)
    row = _row(db)
    row.job_sources = {"linkedin": payload.linkedin, "naukri": payload.naukri}
    invalidate_caches()
    return get_job_sources(db)


def get_live_interview(db: Session) -> dict:
    row = _row(db)
    stored = row.live_interview if isinstance(getattr(row, "live_interview", None), dict) else {}
    merged = {**DEFAULT_LIVE_INTERVIEW, **stored}
    merged["enabled"] = bool(merged.get("enabled"))
    merged["display_name"] = str(merged.get("display_name") or DEFAULT_LIVE_INTERVIEW["display_name"])[:80]
    try:
        merged["price_cents"] = int(merged.get("price_cents") or 0)
    except (TypeError, ValueError):
        merged["price_cents"] = 0
    merged["currency"] = "INR"
    return merged


def get_effective_elevenlabs_api_key(db: Session | None) -> str:
    from backend.app.core.config import settings

    if db is not None:
        row = _row(db)
        db_ai = row.ai if isinstance(getattr(row, "ai", None), dict) else {}
        encrypted = db_ai.get("elevenlabs_api_key_encrypted") or ""
        if encrypted:
            key = decrypt_secret(encrypted)
            if key:
                return key.strip()
            raise AppError(
                "CONFIG_ERROR",
                "The saved ElevenLabs API key could not be decrypted. Re-enter and save it under Admin → Settings → AI "
                "(this usually means SECRET_KEY or JWT_SECRET changed after the key was saved).",
                503,
            )
    return (settings.ELEVENLABS_API_KEY or "").strip()


def get_effective_firecrawl_api_key(db: Session | None) -> str:
    from backend.app.core.config import settings

    if db is not None:
        row = _row(db)
        stored = row.outreach if isinstance(getattr(row, "outreach", None), dict) else {}
        encrypted = stored.get("firecrawl_api_key_encrypted") or ""
        if encrypted:
            key = decrypt_secret(encrypted)
            if key:
                return key.strip()
    return (settings.FIRECRAWL_API_KEY or "").strip()


def _normalize_outreach_campaign(raw: dict | None) -> dict:
    base = dict(DEFAULT_OUTREACH_CAMPAIGN)
    if isinstance(raw, dict):
        for key in base:
            if key in raw and raw[key] is not None:
                base[key] = raw[key]
    base["keywords"] = [str(k).strip() for k in (base.get("keywords") or []) if str(k).strip()]
    base["cities"] = [str(c).strip() for c in (base.get("cities") or []) if str(c).strip()]
    if not base["keywords"]:
        base["keywords"] = list(DEFAULT_OUTREACH_CAMPAIGN["keywords"])
    if not base["cities"]:
        base["cities"] = list(DEFAULT_OUTREACH_CAMPAIGN["cities"])
    sources = base.get("sources") or ["google"]
    base["sources"] = [str(s).strip().lower() for s in sources if str(s).strip()] or ["google"]
    try:
        base["max_results"] = int(base.get("max_results") or DEFAULT_OUTREACH_CAMPAIGN["max_results"])
    except (TypeError, ValueError):
        base["max_results"] = DEFAULT_OUTREACH_CAMPAIGN["max_results"]
    base["max_results"] = max(1, min(50, base["max_results"]))
    try:
        base["rotation_index"] = max(0, int(base.get("rotation_index") or 0))
    except (TypeError, ValueError):
        base["rotation_index"] = 0
    base["public_listing_attestation"] = bool(base.get("public_listing_attestation"))
    for key in ("send_interval_min_sec", "send_interval_max_sec"):
        try:
            base[key] = int(base.get(key) or DEFAULT_OUTREACH_CAMPAIGN[key])
        except (TypeError, ValueError):
            base[key] = DEFAULT_OUTREACH_CAMPAIGN[key]
    if base["send_interval_max_sec"] < base["send_interval_min_sec"]:
        base["send_interval_max_sec"] = base["send_interval_min_sec"]
    return base


def get_outreach_campaign(db: Session) -> dict:
    row = _row(db)
    stored = row.outreach if isinstance(getattr(row, "outreach", None), dict) else {}
    return _normalize_outreach_campaign(stored.get("campaign"))


def save_outreach_campaign(db: Session, campaign: dict) -> dict:
    row = _row(db)
    existing = row.outreach if isinstance(getattr(row, "outreach", None), dict) else {}
    stored = dict(existing)
    stored["campaign"] = _normalize_outreach_campaign(campaign)
    row.outreach = stored
    invalidate_caches()
    return stored["campaign"]


def get_outreach_admin(db: Session) -> dict:
    from backend.app.core.config import settings

    row = _row(db)
    stored = row.outreach if isinstance(getattr(row, "outreach", None), dict) else {}
    env_key = (settings.FIRECRAWL_API_KEY or "").strip()
    db_configured = bool(stored.get("firecrawl_api_key_encrypted"))
    provider = str(stored.get("whatsapp_provider") or "bridge").strip().lower()
    if provider not in ("bridge", "cloud"):
        provider = "bridge"
    from backend.app.services import whatsapp_cloud_client
    return {
        "firecrawl_api_key_configured": db_configured or bool(env_key),
        "source": "database" if db_configured else ("environment" if env_key else "none"),
        "campaign": get_outreach_campaign(db),
        "automation_enabled": settings.OUTREACH_AUTOMATION_ENABLED,
        "whatsapp_provider": provider,
        "whatsapp_cloud_configured": whatsapp_cloud_client.configured(),
    }


def update_outreach(db: Session, payload: OutreachSettingsIn) -> dict:
    if payload.firecrawl_api_key and _fernet() is None:
        raise AppError("CONFIG_ERROR", "Set SECRET_KEY or JWT_SECRET (32+ chars) before saving API keys.", 503)
    row = _row(db)
    existing = row.outreach if isinstance(getattr(row, "outreach", None), dict) else {}
    stored = dict(existing)
    if payload.firecrawl_api_key:
        stored["firecrawl_api_key_encrypted"] = encrypt_secret(payload.firecrawl_api_key.strip())
    elif existing.get("firecrawl_api_key_encrypted"):
        stored["firecrawl_api_key_encrypted"] = existing["firecrawl_api_key_encrypted"]
    if payload.campaign is not None:
        current = _normalize_outreach_campaign(stored.get("campaign"))
        incoming = payload.campaign.model_dump()
        for key, value in incoming.items():
            current[key] = value
        stored["campaign"] = _normalize_outreach_campaign(current)
    if payload.whatsapp_provider:
        stored["whatsapp_provider"] = payload.whatsapp_provider
    row.outreach = stored
    invalidate_caches()
    return get_outreach_admin(db)


def get_gst_admin(db: Session) -> dict:
    from backend.app.services import gst_service

    row = _row(db)
    stored = row.gst if isinstance(getattr(row, "gst", None), dict) else {}
    return gst_service.gst_admin_view(stored)


def update_gst(db: Session, payload: GstSettingsIn) -> dict:
    from backend.app.services import gst_service

    row = _row(db)
    existing = row.gst if isinstance(getattr(row, "gst", None), dict) else {}
    merged = {**existing, **payload.model_dump()}
    normalized = gst_service.normalize_gst_settings(merged, strict=True)
    gst_service.validate_gst_settings_for_enable(normalized)
    row.gst = normalized
    invalidate_caches()
    return get_gst_admin(db)


def update_live_interview(db: Session, payload: LiveInterviewSettingsIn) -> dict:
    row = _row(db)
    row.live_interview = {
        "enabled": payload.enabled,
        "display_name": payload.display_name.strip(),
        "price_cents": payload.price_cents,
        "currency": "INR",
    }
    invalidate_caches()
    return get_live_interview(db)


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
    if (payload.api_key or payload.elevenlabs_api_key) and _fernet() is None:
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
    if payload.elevenlabs_api_key:
        stored["elevenlabs_api_key_encrypted"] = encrypt_secret(payload.elevenlabs_api_key.strip())
    elif existing.get("elevenlabs_api_key_encrypted"):
        stored["elevenlabs_api_key_encrypted"] = existing["elevenlabs_api_key_encrypted"]
    from backend.app.core.platform_defaults import DEFAULT_AI

    if payload.mock_interview_presenter is not None:
        stored["mock_interview_presenter"] = payload.mock_interview_presenter.model_dump()
    elif isinstance(existing.get("mock_interview_presenter"), dict):
        stored["mock_interview_presenter"] = existing["mock_interview_presenter"]
    else:
        stored["mock_interview_presenter"] = dict(DEFAULT_AI.get("mock_interview_presenter") or {})
    if payload.mock_interview_voice is not None:
        prior = existing.get("mock_interview_voice") if isinstance(existing.get("mock_interview_voice"), dict) else {}
        stored["mock_interview_voice"] = {**prior, **payload.mock_interview_voice.model_dump()}
    elif isinstance(existing.get("mock_interview_voice"), dict):
        stored["mock_interview_voice"] = existing["mock_interview_voice"]
    else:
        stored["mock_interview_voice"] = dict(DEFAULT_AI.get("mock_interview_voice") or {})
    prior_unlimited = existing.get("mock_interviews_unlimited_emails")
    if isinstance(prior_unlimited, list):
        stored["mock_interviews_unlimited_emails"] = prior_unlimited
    else:
        stored["mock_interviews_unlimited_emails"] = list(DEFAULT_AI.get("mock_interviews_unlimited_emails") or [])
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

    cms = row.cms or {}
    contact = (cms.get("branding") or {}).get("contact_email") or ""
    if contact.strip() in ("", "support@applyxai.example"):
        merged_cms = _deep_merge(dict(DEFAULT_CMS), cms)
        merged_cms.setdefault("branding", {})["contact_email"] = "support@applyxai.com"
        row.cms = merged_cms
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
