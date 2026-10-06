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

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "ApplyXAI <no-reply@localhost>"

    PAYMENT_PROVIDER: Literal["null", "razorpay"] = "null"
    PAYMENT_KEY_ID: str = ""
    PAYMENT_SECRET: str = ""
    PAYMENT_WEBHOOK_SECRET: str = ""

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _blank_database_url_means_default(cls, value):
        return value if value not in (None, "") else _DEFAULT_DATABASE_URL

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

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
        if problems:
            raise ValueError("Invalid production configuration: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
