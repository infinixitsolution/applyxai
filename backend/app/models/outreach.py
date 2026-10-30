"""Admin institute discovery, enrichment, and outbound marketing."""

import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, JSONType, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin


class InstituteScrapeJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "institute_scrape_jobs"

    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    owner_institute_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institutes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    query: Mapped[str] = mapped_column(String(500))
    location: Mapped[str] = mapped_column(String(190), default="")
    sources: Mapped[list] = mapped_column(JSONType, default=list)
    max_results: Mapped[int] = mapped_column(Integer, default=25)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    leads_found: Mapped[int] = mapped_column(Integer, default=0)
    leads_updated: Mapped[int] = mapped_column(Integer, default=0)
    leads_enriched: Mapped[int] = mapped_column(Integer, default=0)
    stats: Mapped[dict] = mapped_column(JSONType, default=dict)
    error_message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    leads: Mapped[list["InstituteLead"]] = relationship(back_populates="job")


class InstituteLead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "institute_leads"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_institute_leads_dedupe_key"),)

    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institute_scrape_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_platform: Mapped[str] = mapped_column(String(32), default="google", index=True)
    source_url: Mapped[str] = mapped_column(String(2000), default="")
    dedupe_key: Mapped[str] = mapped_column(String(512), index=True)
    display_name: Mapped[str] = mapped_column(String(190), default="")
    status: Mapped[str] = mapped_column(String(32), default="discovered", index=True)
    institute_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institutes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    owner_institute_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institutes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    completeness_score: Mapped[int] = mapped_column(Integer, default=0)
    whatsapp_phone: Mapped[str] = mapped_column(String(32), default="", index=True)

    job: Mapped[InstituteScrapeJob | None] = relationship(back_populates="leads")
    profile: Mapped["InstituteLeadProfile | None"] = relationship(back_populates="lead", uselist=False)
    messages: Mapped[list["InstituteOutreachMessage"]] = relationship(back_populates="lead")
    chat_messages: Mapped[list["InstituteLeadChatMessage"]] = relationship(back_populates="lead")


class InstituteLeadProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "institute_lead_profiles"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institute_leads.id", ondelete="CASCADE"), unique=True, index=True
    )
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    raw_snippets: Mapped[list] = mapped_column(JSONType, default=list)

    lead: Mapped[InstituteLead] = relationship(back_populates="profile")


class InstituteOutreachMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "institute_outreach_messages"

    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institute_leads.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(16), index=True)
    subject: Mapped[str] = mapped_column(String(500), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    html: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    provider_response: Mapped[str] = mapped_column(Text, default="")
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    lead: Mapped[InstituteLead] = relationship(back_populates="messages")


class InstituteLeadChatMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "institute_lead_chat_messages"
    __table_args__ = (
        UniqueConstraint("external_id", name="uq_institute_lead_chat_external_id"),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institute_leads.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(16), default="whatsapp")
    direction: Mapped[str] = mapped_column(String(16), index=True)  # inbound | outbound
    body: Mapped[str] = mapped_column(Text, default="")
    external_id: Mapped[str] = mapped_column(String(190), default="")

    lead: Mapped[InstituteLead] = relationship(back_populates="chat_messages")


class WhatsAppSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "whatsapp_sessions"

    session_key: Mapped[str] = mapped_column(String(32), unique=True, default="default")
    status: Mapped[str] = mapped_column(String(32), default="disconnected")
    session_path: Mapped[str] = mapped_column(String(500), default="")
    connected_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
