import uuid

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from backend.app.models.enums import MockInterviewMessageRole, MockInterviewSessionStatus


class MockInterviewSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mock_interview_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    interview_types: Mapped[list] = mapped_column(JSONType, default=list)
    status: Mapped[MockInterviewSessionStatus] = mapped_column(
        str_enum(MockInterviewSessionStatus, "mock_interview_session_status"),
        default=MockInterviewSessionStatus.ACTIVE,
    )
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    feedback: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    context_snapshot: Mapped[dict] = mapped_column(JSONType, default=dict)

    messages: Mapped[list["MockInterviewMessage"]] = relationship(
        back_populates="session", order_by="MockInterviewMessage.created_at"
    )

    __table_args__ = (Index("ix_mock_interview_sessions_user_created", "user_id", "created_at"),)


class MockInterviewMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mock_interview_messages"

    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mock_interview_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[MockInterviewMessageRole] = mapped_column(
        str_enum(MockInterviewMessageRole, "mock_interview_message_role"),
    )
    content: Mapped[str] = mapped_column(Text, default="")
    client_turn_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONType, nullable=True)

    session: Mapped[MockInterviewSession] = relationship(back_populates="messages")

    __table_args__ = (
        Index("ix_mock_interview_messages_session_created", "session_id", "created_at"),
        Index("uq_mock_interview_messages_session_client_turn", "session_id", "client_turn_id", unique=True),
    )
