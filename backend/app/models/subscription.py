import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, JSONType, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin, str_enum
from backend.app.models.enums import PlanKind, SubscriptionStatus


class Plan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Plan catalogue. Limits and prices live here (seeded from config), never in code paths."""

    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[PlanKind] = mapped_column(
        str_enum(PlanKind, "plan_kind"), default=PlanKind.PERSONAL, server_default="personal"
    )
    limits: Mapped[dict] = mapped_column(JSONType, default=dict)
    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    interval: Mapped[str] = mapped_column(String(16), default="month")
    provider_plan_id: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    institute_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institutes.id", ondelete="SET NULL"), index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"), index=True)
    status: Mapped[SubscriptionStatus] = mapped_column(
        str_enum(SubscriptionStatus, "subscription_status"), default=SubscriptionStatus.PENDING, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), default="")
    provider_customer_id: Mapped[str] = mapped_column(String(255), default="")
    provider_subscription_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    current_period_start: Mapped[datetime | None] = mapped_column(UTCDateTime())
    current_period_end: Mapped[datetime | None] = mapped_column(UTCDateTime())
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)

    plan: Mapped[Plan] = relationship()
