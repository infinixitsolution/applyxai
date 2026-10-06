import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin


class AdminAction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Audit trail of every change an admin makes. Rows are only ever added."""

    __tablename__ = "admin_actions"

    admin_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    admin_email: Mapped[str] = mapped_column(String(320), default="")
    action: Mapped[str] = mapped_column(String(64))
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    target: Mapped[str] = mapped_column(String(320), default="")
    details: Mapped[dict] = mapped_column(JSONType, default=dict)
