import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, JSONType, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin, str_enum
from backend.app.models.enums import (
    CommissionStatus,
    KycStatus,
    PartnerCommissionMode,
    PartnerStatus,
    PayoutStatus,
)


class Partner(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "partners"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    organization: Mapped[str] = mapped_column(String(190), default="")
    contact_name: Mapped[str] = mapped_column(String(190), default="")
    phone: Mapped[str] = mapped_column(String(32), default="")
    referral_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    status: Mapped[PartnerStatus] = mapped_column(
        str_enum(PartnerStatus, "partner_status"), default=PartnerStatus.PENDING, index=True
    )
    kyc_status: Mapped[KycStatus] = mapped_column(
        str_enum(KycStatus, "kyc_status"), default=KycStatus.PENDING
    )
    commission_mode: Mapped[PartnerCommissionMode] = mapped_column(
        str_enum(PartnerCommissionMode, "partner_commission_mode"),
        default=PartnerCommissionMode.PERCENT_PAYMENT,
    )
    commission_bps: Mapped[int] = mapped_column(Integer, default=2000)
    commission_flat_cents: Mapped[int] = mapped_column(Integer, default=0)
    gstin: Mapped[str] = mapped_column(String(15), default="")
    pan_number: Mapped[str] = mapped_column(String(10), default="")
    payout_account: Mapped[str] = mapped_column(String(255), default="")
    payout_ifsc: Mapped[str] = mapped_column(String(20), default="")
    kyc_documents: Mapped[list] = mapped_column(JSONType, default=list)
    click_count: Mapped[int] = mapped_column(Integer, default=0)


class PartnerAttribution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "partner_attributions"
    __table_args__ = (UniqueConstraint("partner_id", "institute_id"),)

    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("partners.id", ondelete="CASCADE"), index=True)
    institute_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutes.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(32), default="referral")


class PartnerCommission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "partner_commissions"
    __table_args__ = (
        UniqueConstraint("payment_id"),
        UniqueConstraint("assignment_id"),
    )

    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("partners.id", ondelete="CASCADE"), index=True)
    institute_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("institutes.id", ondelete="SET NULL"), index=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("subscriptions.id", ondelete="SET NULL"))
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payments.id", ondelete="SET NULL"))
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institute_assignments.id", ondelete="SET NULL"), index=True
    )
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    commission_mode: Mapped[PartnerCommissionMode] = mapped_column(
        str_enum(PartnerCommissionMode, "partner_commission_mode"),
        default=PartnerCommissionMode.PERCENT_PAYMENT,
    )
    rate_bps: Mapped[int] = mapped_column(Integer, default=2000)
    rate_flat_cents: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[CommissionStatus] = mapped_column(
        str_enum(CommissionStatus, "commission_status"), default=CommissionStatus.ACCRUED, index=True
    )
    note: Mapped[str] = mapped_column(String(255), default="")


class PartnerPayout(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "partner_payouts"

    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("partners.id", ondelete="CASCADE"), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[PayoutStatus] = mapped_column(
        str_enum(PayoutStatus, "payout_status"), default=PayoutStatus.REQUESTED, index=True
    )
    note: Mapped[str] = mapped_column(Text, default="")
    processed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class PartnerCampaign(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "partner_campaigns"
    __table_args__ = (UniqueConstraint("partner_id", "code"),)

    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("partners.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(32))
    click_count: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(String(255), default="")
