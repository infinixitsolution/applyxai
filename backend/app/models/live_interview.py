"""Paid live-interview tokens, sessions, and the private support thread that sells them."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, JSONType, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin


class SupportThread(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "support_threads"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    last_message_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class SupportMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "support_messages"

    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("support_threads.id", ondelete="CASCADE"), index=True)
    sender: Mapped[str] = mapped_column(String(16), default="user")  # user, admin, system
    kind: Mapped[str] = mapped_column(String(32), default="text")  # text, payment_link, token
    body: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[dict | None] = mapped_column(JSONType, nullable=True)

    __table_args__ = (Index("ix_support_messages_thread_created", "thread_id", "created_at"),)


class LiveInterviewOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "live_interview_orders"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("support_threads.id", ondelete="CASCADE"), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    provider: Mapped[str] = mapped_column(String(32), default="null")
    provider_link_id: Mapped[str] = mapped_column(String(128), default="")
    provider_link_url: Mapped[str] = mapped_column(String(1024), default="")
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending, paid


class LiveInterviewToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "live_interview_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("live_interview_orders.id", ondelete="CASCADE"), unique=True)
    code: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="unused")  # unused, reserved, used
    session_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)


class LiveInterviewSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "live_interview_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("live_interview_tokens.id", ondelete="CASCADE"), unique=True)
    application_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("applications.id", ondelete="SET NULL"), nullable=True)
    job_title: Mapped[str] = mapped_column(String(500), default="")
    company: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(16), default="active")  # active, completed
    transcript: Mapped[list] = mapped_column(JSONType, default=list)
    feedback: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime())
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    __table_args__ = (Index("ix_live_interview_sessions_user_created", "user_id", "created_at"),)
