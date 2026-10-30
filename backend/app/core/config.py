"""Application settings, read from environment variables (and `.env` at the project root)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STORAGE_DIR = PROJECT_ROOT / "storage"
_DEFAULT_DATABASE_URL = f"sqlite:///{(DEFAULT_STORAGE_DIR / 'applyxai.db').as_posix()}"
# Shared with whatsapp-bridge/start script in development when .env omits WHATSAPP_BRIDGE_SECRET.
DEV_WHATSAPP_BRIDGE_SECRET = "dev-whatsapp-bridge-local"


def _agent_latest_version() -> str:
    try:
        text = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        if text:
            return text.splitlines()[0].strip()
    except OSError:
        pass
    return "1.2.21"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "ApplyXAI"
    APP_ENV: Literal["development", "test", "production"] = "development"
    # When true, Naukri is treated as enabled in job_sources (staging/local smoke without admin toggle).
    ENABLE_NAUKRI: bool = False
    APP_VERSION: str = "0.1.0"

    SECRET_KEY: str = ""
    JWT_SECRET: str = ""

    # SQLite keeps local development dependency-free; production must use PostgreSQL.
    DATABASE_URL: str = _DEFAULT_DATABASE_URL
    DATABASE_ECHO: bool = False
    REDIS_URL: str = "redis://localhost:6379/0"

    # Comma-separated list of browser origins allowed to call the API with credentials.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    STORAGE_DIR: Path = DEFAULT_STORAGE_DIR
    MAX_RESUME_BYTES: int = 5 * 1024 * 1024
    # Optional ClamAV (clamd) INSTREAM scan on resume upload; leave empty to disable.
    CLAMAV_HOST: str = ""
    CLAMAV_PORT: int = 3310
    CLAMAV_SCAN_TIMEOUT_SEC: float = 30.0
    # ApplyXAI Desktop — single Windows installer (Electron + embedded automation worker).
    DESKTOP_APP_SETUP_PATH: Path = PROJECT_ROOT / "dist" / "ApplyXAI-Desktop-Setup.exe"
    DESKTOP_APP_ZIP_PATH: Path = PROJECT_ROOT / "dist" / "ApplyXAI-Desktop-Windows.zip"
    # Legacy standalone agent (deprecated; kept for old deployments only).
    DESKTOP_AGENT_SETUP_PATH: Path = PROJECT_ROOT / "dist" / "ApplyXAI-Agent-Setup.exe"
    DESKTOP_AGENT_GUI_PATH: Path = PROJECT_ROOT / "dist" / "ApplyXAI-Agent-GUI.exe"
    DESKTOP_AGENT_ZIP_PATH: Path = PROJECT_ROOT / "dist" / "ApplyXAI-Agent-Windows.zip"
    AGENT_LATEST_VERSION: str = _agent_latest_version()
    AGENT_DOWNLOAD_URL: str = ""

    FIRECRAWL_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""
    # Comma-separated account emails with unlimited mock interviews (plan cap ignored for mock only).
    MOCK_INTERVIEWS_UNLIMITED_EMAILS: str = ""
    WHATSAPP_BRIDGE_URL: str = "http://127.0.0.1:39219"
    WHATSAPP_BRIDGE_SECRET: str = ""
    # Meta WhatsApp Cloud API (optional; unofficial bridge remains the local/dev path).
    WHATSAPP_CLOUD_TOKEN: str = ""
    WHATSAPP_CLOUD_PHONE_NUMBER_ID: str = ""
    WHATSAPP_CLOUD_WABA_ID: str = ""
    WHATSAPP_CLOUD_VERIFY_TOKEN: str = ""
    WHATSAPP_CLOUD_APP_SECRET: str = ""
    # RazorpayX current-account number for partner payouts (Pay now). Empty = manual transfer only.
    RAZORPAYX_ACCOUNT_NUMBER: str = ""
    RAZORPAYX_KEY_ID: str = ""
    RAZORPAYX_KEY_SECRET: str = ""
    APPLYXAI_API_URL: str = "http://127.0.0.1:8010"
    OUTREACH_MAX_LEADS_PER_JOB: int = 50
    OUTREACH_AUTOMATION_ENABLED: bool = True

    # Where the SPA lives; used to build links in verification / reset emails.
    FRONTEND_URL: str = "http://localhost:5173"

    ACCESS_TOKEN_MINUTES: int = 15
    REFRESH_TOKEN_DAYS: int = 30
    EMAIL_VERIFICATION_HOURS: int = 24
    PASSWORD_RESET_MINUTES: int = 60
    REQUIRE_EMAIL_VERIFICATION: bool = True
    # None = Secure cookies exactly when APP_ENV is production.
    COOKIE_SECURE: bool | None = None

    # "memory://" is per-process (fine for one dev server); use Redis in production.
    RATE_LIMIT_STORAGE_URL: str = "memory://"

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "ApplyXAI <no-reply@localhost>"

    PAYMENT_PROVIDER: Literal["null", "razorpay", "stripe"] = "null"
    PAYMENT_KEY_ID: str = ""
    PAYMENT_SECRET: str = ""
    PAYMENT_WEBHOOK_SECRET: str = ""
    # When true and PAYMENT_PROVIDER=null, /billing/checkout still grants plans without Razorpay (local dev only).
    PAYMENT_DEV_INSTANT_CHECKOUT: bool = False

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _blank_database_url_means_default(cls, value):
        return value if value not in (None, "") else _DEFAULT_DATABASE_URL

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def _resolve_sqlite_relative_to_project(cls, value: str) -> str:
        """Anchor `sqlite:///storage/...` to the repo root, not the process cwd (avoids backend/ vs root split)."""
        prefix = "sqlite:///"
        if not value.startswith(prefix):
            return value
        rest = value[len(prefix) :].replace("\\", "/")
        if rest.startswith("/") or (len(rest) > 1 and rest[1] == ":"):
            return value
        # Strip leading `./` or `../` so `sqlite:///../storage/applyxai.db` still lands in project storage.
        while rest.startswith("../"):
            rest = rest[3:]
        while rest.startswith("./"):
            rest = rest[2:]
        resolved = (PROJECT_ROOT / rest).resolve().as_posix()
        return f"{prefix}{resolved}"

    @field_validator("COOKIE_SECURE", mode="before")
    @classmethod
    def _blank_means_auto(cls, value):
        return None if value == "" else value

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def cookie_secure(self) -> bool:
        return self.APP_ENV == "production" if self.COOKIE_SECURE is None else self.COOKIE_SECURE

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @model_validator(mode="after")
    def _development_whatsapp_bridge_secret(self) -> "Settings":
        if self.APP_ENV != "production" and not (self.WHATSAPP_BRIDGE_SECRET or "").strip():
            object.__setattr__(self, "WHATSAPP_BRIDGE_SECRET", DEV_WHATSAPP_BRIDGE_SECRET)
        return self

    @model_validator(mode="after")
    def _production_requirements(self) -> "Settings":
        if self.APP_ENV != "production":
            return self
        problems = []
        if self.OUTREACH_AUTOMATION_ENABLED and not (self.WHATSAPP_BRIDGE_SECRET or "").strip():
            problems.append(
                "WHATSAPP_BRIDGE_SECRET must be set when OUTREACH_AUTOMATION_ENABLED is true (inbound WhatsApp)"
            )
        if len(self.SECRET_KEY) < 32:
            problems.append("SECRET_KEY must be set to at least 32 characters")
        if len(self.JWT_SECRET) < 32:
            problems.append("JWT_SECRET must be set to at least 32 characters")
        if self.is_sqlite:
            problems.append("DATABASE_URL must point at PostgreSQL")
        if self.PAYMENT_PROVIDER == "null":
            problems.append("PAYMENT_PROVIDER 'null' grants plans for free and is not allowed")
        elif self.PAYMENT_PROVIDER not in ("razorpay", "stripe"):
            problems.append("PAYMENT_PROVIDER must be razorpay or stripe in production")
        elif not (self.PAYMENT_KEY_ID and self.PAYMENT_SECRET and self.PAYMENT_WEBHOOK_SECRET):
            problems.append("PAYMENT_KEY_ID, PAYMENT_SECRET, and PAYMENT_WEBHOOK_SECRET must be set")
        # SMTP may be configured in the admin settings table after deploy.
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE cannot be disabled in production")
        if self.RATE_LIMIT_STORAGE_URL.startswith("memory"):
            problems.append("RATE_LIMIT_STORAGE_URL must be shared storage (Redis) in production")
        if problems:
            raise ValueError("Invalid production configuration: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
