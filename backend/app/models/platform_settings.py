from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.platform_defaults import DEFAULT_AI, DEFAULT_CMS, DEFAULT_NOTIFICATIONS, DEFAULT_PAYMENTS, PLATFORM_SETTINGS_KEY
from backend.app.models.base import Base, JSONType, TimestampMixin


class PlatformSettings(TimestampMixin, Base):
    """Singleton platform configuration (CMS, SMTP overrides, auth policy, notification toggles)."""

    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(32), primary_key=True, default=PLATFORM_SETTINGS_KEY)
    cms: Mapped[dict] = mapped_column(JSONType, default=lambda: dict(DEFAULT_CMS))
    smtp: Mapped[dict] = mapped_column(JSONType, default=dict)
    auth_email: Mapped[dict] = mapped_column(JSONType, default=dict)
    notifications: Mapped[dict] = mapped_column(JSONType, default=lambda: dict(DEFAULT_NOTIFICATIONS))
    ai: Mapped[dict] = mapped_column(JSONType, default=lambda: dict(DEFAULT_AI))
    payments: Mapped[dict] = mapped_column(JSONType, default=lambda: dict(DEFAULT_PAYMENTS))
