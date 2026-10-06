from datetime import datetime

from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin, utcnow


class Job(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Shared catalogue of postings, one row per (platform, external_id). Users never list
    this table directly: user-facing queries always join through their own applications.
    """

    __tablename__ = "jobs"

    external_id: Mapped[str] = mapped_column(String(64), index=True)
    platform: Mapped[str] = mapped_column(String(32), default="linkedin", index=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    company: Mapped[str] = mapped_column(String(255), default="", index=True)
    location: Mapped[str] = mapped_column(String(255), default="")
    job_url: Mapped[str] = mapped_column(String(1024), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    employment_type: Mapped[str] = mapped_column(String(32), default="")
    work_setting: Mapped[str] = mapped_column(String(32), default="")
    experience_level: Mapped[str] = mapped_column(String(32), default="")
    discovered_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)

    __table_args__ = (UniqueConstraint("platform", "external_id"),)
