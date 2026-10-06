import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A charge reported by the payment provider. Card details never reach ApplyXAI."""

    __tablename__ = "payments"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="SET NULL"), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    provider_payment_id: Mapped[str] = mapped_column(String(255), unique=True)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[str] = mapped_column(String(32), default="")
    method: Mapped[str] = mapped_column(String(32), default="")
    description: Mapped[str] = mapped_column(String(255), default="")
    paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class BillingEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One processed provider webhook, so a redelivered event is applied only once. Only the type
    and the IDs are kept, never the payload (it carries the customer's contact details).
    """

    __tablename__ = "billing_events"

    provider: Mapped[str] = mapped_column(String(32))
    event_id: Mapped[str] = mapped_column(String(255))
    event_type: Mapped[str] = mapped_column(String(64), default="")
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("subscriptions.id", ondelete="SET NULL"))

    __table_args__ = (UniqueConstraint("provider", "event_id"),)
