"""Admin company directory — web-sourced HR contacts and job links."""

from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin, UTCDateTime


class CompanyDirectoryProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "company_directory_profiles"

    company_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(32), default="idle", index=True)
    contacts: Mapped[list] = mapped_column(JSONType, default=list)
    job_links: Mapped[list] = mapped_column(JSONType, default=list)
    source_pages: Mapped[list] = mapped_column(JSONType, default=list)
    last_enriched_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="")
