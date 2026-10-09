import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, UTCDateTime, UUIDPrimaryKeyMixin


class AgentConnectSession(UUIDPrimaryKeyMixin, Base):
    """Short-lived session for browser one-click desktop agent pairing."""

    __tablename__ = "agent_connect_sessions"

    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    requested_name: Mapped[str] = mapped_column(String(100), default="")
    platform: Mapped[str] = mapped_column(String(50), default="")
    agent_version: Mapped[str] = mapped_column(String(32), default="")
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_devices.id", ondelete="SET NULL"), nullable=True,
    )
    deliver_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
