import pytest
from pydantic import ValidationError

from backend.app.core.config import Settings

STRONG = "x" * 40


def test_development_defaults_need_no_environment():
    s = Settings(_env_file=None)
    assert s.APP_ENV == "development"
    assert s.is_sqlite
    assert "http://localhost:5173" in s.cors_origins


def test_env_example_works_as_a_dev_env_file():
    '''Copying .env.example to .env unchanged must give a working development setup.'''
    from backend.app.core.config import PROJECT_ROOT
    s = Settings(_env_file=PROJECT_ROOT / ".env.example")
    assert s.APP_ENV == "development"
    assert s.DATABASE_URL.startswith("sqlite:///") and s.DATABASE_URL.endswith("storage/applyxai.db")
    assert s.PAYMENT_PROVIDER == "null"
    assert s.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_production_rejects_missing_secrets_and_sqlite():
    with pytest.raises(ValidationError) as err:
        Settings(_env_file=None, APP_ENV="production")
    message = str(err.value)
    assert "SECRET_KEY" in message and "JWT_SECRET" in message and "PostgreSQL" in message


PRODUCTION_OK = dict(
    _env_file=None, APP_ENV="production", SECRET_KEY=STRONG, JWT_SECRET=STRONG,
    DATABASE_URL="postgresql+psycopg://u:p@db/applyxai", PAYMENT_PROVIDER="razorpay",
    SMTP_HOST="smtp.example.com", RATE_LIMIT_STORAGE_URL="redis://redis:6379/1",
)


@pytest.mark.parametrize("override, expected", [
    ({"PAYMENT_PROVIDER": "null"}, "PAYMENT_PROVIDER"),
    ({"SMTP_HOST": ""}, "SMTP_HOST"),
    ({"COOKIE_SECURE": False}, "COOKIE_SECURE"),
    ({"RATE_LIMIT_STORAGE_URL": "memory://"}, "RATE_LIMIT_STORAGE_URL"),
])
def test_production_rejects_unsafe_settings(override, expected):
    with pytest.raises(ValidationError, match=expected):
        Settings(**{**PRODUCTION_OK, **override})


def test_valid_production_configuration():
    s = Settings(**PRODUCTION_OK, CORS_ORIGINS="https://app.applyxai.com , https://applyxai.com")
    assert s.cors_origins == ["https://app.applyxai.com", "https://applyxai.com"]
    assert s.cookie_secure is True


def test_cookies_are_not_secure_in_development():
    assert Settings(_env_file=None).cookie_secure is False
