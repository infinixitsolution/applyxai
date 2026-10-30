import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin


class CandidateReferral(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Candidate-to-candidate attribution. Never mixed with partner commissions."""

    __tablename__ = "candidate_referrals"
    __table_args__ = (UniqueConstraint("referred_user_id"),)

    referrer_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    referred_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(16), default="attributed")
    converted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
