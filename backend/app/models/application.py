import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from backend.app.models.enums import ApplicationStatus
from backend.app.models.job import Job


class Application(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "applications"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    resume_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("resumes.id", ondelete="SET NULL"))
    automation_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("automation_jobs.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        str_enum(ApplicationStatus, "application_status"), default=ApplicationStatus.DISCOVERED
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str] = mapped_column(Text, default="")
    external_application_id: Mapped[str] = mapped_column(String(255), default="")

    job: Mapped[Job] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "job_id"),
        Index("ix_applications_user_status", "user_id", "status"),
        Index("ix_applications_user_applied_at", "user_id", "applied_at"),
    )
