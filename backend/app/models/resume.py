import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Resume(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "resumes"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    # Original upload name, for display only. Never used to build a path.
    filename: Mapped[str] = mapped_column(String(255))
    # Generated server-side (UUID based), relative to STORAGE_DIR.
    storage_path: Mapped[str] = mapped_column(String(512), unique=True)
    file_type: Mapped[str] = mapped_column(String(16))
    file_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index(
            "uq_resumes_one_default_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_default"),
            sqlite_where=text("is_default"),
        ),
    )
