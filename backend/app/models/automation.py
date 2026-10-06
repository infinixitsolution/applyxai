import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin, str_enum
from backend.app.models.enums import ACTIVE_AUTOMATION_STATUSES, AutomationStatus

_ACTIVE_STATUS_SQL = text(
    "status IN (" + ", ".join(f"'{s.value}'" for s in ACTIVE_AUTOMATION_STATUSES) + ")"
)


class AutomationJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "automation_jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[AutomationStatus] = mapped_column(
        str_enum(AutomationStatus, "automation_status"), default=AutomationStatus.QUEUED, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    current_job: Mapped[str] = mapped_column(String(500), default="")
    total_jobs: Mapped[int] = mapped_column(Integer, default=0)
    successful_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, default="")
    task_id: Mapped[str] = mapped_column(String(255), default="")
    worker_id: Mapped[str] = mapped_column(String(255), default="")

    __table_args__ = (
        # At most one queued/running/paused run per user, enforced by the database.
        Index(
            "uq_automation_jobs_one_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=_ACTIVE_STATUS_SQL,
            sqlite_where=_ACTIVE_STATUS_SQL,
        ),
    )


class AutomationLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One line of a run's activity log. `seq` numbers lines within a run for polling with ?after=."""

    __tablename__ = "automation_logs"

    automation_job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("automation_jobs.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    ts: Mapped[datetime] = mapped_column(UTCDateTime())
    level: Mapped[str] = mapped_column(String(10), default="info")
    event: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text, default="")

    __table_args__ = (Index("uq_automation_logs_run_seq", "automation_job_id", "seq", unique=True),)
