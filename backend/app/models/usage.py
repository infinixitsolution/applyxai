import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UsageCounter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-user, per-calendar-month usage. Resume count is derived from the resumes table."""

    __tablename__ = "usage_counters"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    period: Mapped[str] = mapped_column(String(7))  # "YYYY-MM", UTC
    applications: Mapped[int] = mapped_column(Integer, default=0)
    jobs_discovered: Mapped[int] = mapped_column(Integer, default=0)
    runtime_seconds: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (UniqueConstraint("user_id", "period"),)
