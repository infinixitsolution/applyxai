import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin


class AgentDevice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A computer running the ApplyXAI desktop agent. It's created with a short single-use
    pairing code, which the agent exchanges for a long-lived device token. Only SHA-256
    hashes of the code and the token are stored.
    """

    __tablename__ = "agent_devices"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100), default="")
    platform: Mapped[str] = mapped_column(String(50), default="")
    agent_version: Mapped[str] = mapped_column(String(32), default="")
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    pairing_code_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    pairing_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    paired_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
