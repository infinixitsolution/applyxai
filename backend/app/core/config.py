"""Application settings, read from environment variables (and `.env` at the project root)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STORAGE_DIR = PROJECT_ROOT / "storage"
_DEFAULT_DATABASE_URL = f"sqlite:///{(DEFAULT_STORAGE_DIR / 'applyxai.db').as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "ApplyXAI"
    APP_ENV: Literal["development", "test", "production"] = "development"
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
    # Desktop agent download: prefer single Setup.exe, else GUI-only fallback.
    DESKTOP_AGENT_SETUP_PATH: Path = PROJECT_ROOT / "dist" / "ApplyXAI-Agent-Setup.exe"
    DESKTOP_AGENT_GUI_PATH: Path = PROJECT_ROOT / "dist" / "ApplyXAI-Agent-GUI.exe"

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

    PAYMENT_PROVIDER: Literal["null", "razorpay"] = "null"
    PAYMENT_KEY_ID: str = ""
    PAYMENT_SECRET: str = ""
    PAYMENT_WEBHOOK_SECRET: str = ""
    # When true and PAYMENT_PROVIDER=null, /billing/checkout still grants plans without Razorpay (local dev only).
    PAYMENT_DEV_INSTANT_CHECKOUT: bool = False

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _blank_database_url_means_default(cls, value):
        return value if value not in (None, "") else _DEFAULT_DATABASE_URL

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
    def _production_requirements(self) -> "Settings":
        if self.APP_ENV != "production":
            return self
        problems = []
        if len(self.SECRET_KEY) < 32:
            problems.append("SECRET_KEY must be set to at least 32 characters")
        if len(self.JWT_SECRET) < 32:
            problems.append("JWT_SECRET must be set to at least 32 characters")
        if self.is_sqlite:
            problems.append("DATABASE_URL must point at PostgreSQL")
        if self.PAYMENT_PROVIDER == "null":
            problems.append("PAYMENT_PROVIDER 'null' grants plans for free and is not allowed")
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
