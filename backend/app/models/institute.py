import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, JSONType, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin, str_enum
from backend.app.models.enums import AssignmentStatus, InstituteMemberRole, InstituteStatus, SeatStatus


class Institute(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "institutes"

    name: Mapped[str] = mapped_column(String(190))
    email: Mapped[str] = mapped_column(String(320), index=True)
    contact_name: Mapped[str] = mapped_column(String(190), default="")
    phone: Mapped[str] = mapped_column(String(32), default="")
    institute_type: Mapped[str] = mapped_column(String(32), default="OTHER")
    gstin: Mapped[str] = mapped_column(String(15), default="")
    pan_number: Mapped[str] = mapped_column(String(10), default="")
    status: Mapped[InstituteStatus] = mapped_column(
        str_enum(InstituteStatus, "institute_status"), default=InstituteStatus.PENDING, index=True
    )
    partner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("partners.id", ondelete="SET NULL"), index=True)
    source: Mapped[str] = mapped_column(String(16), default="direct")
    claimed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    settings: Mapped[dict] = mapped_column(JSONType, default=dict)

    members: Mapped[list["InstituteMember"]] = relationship(back_populates="institute")
    seats: Mapped[list["InstituteSeat"]] = relationship(back_populates="institute")
    assignments: Mapped[list["InstituteAssignment"]] = relationship(back_populates="institute")


class InstituteMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "institute_members"
    __table_args__ = (UniqueConstraint("institute_id", "user_id"),)

    institute_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutes.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[InstituteMemberRole] = mapped_column(
        str_enum(InstituteMemberRole, "institute_member_role"), default=InstituteMemberRole.ADMIN
    )
    status: Mapped[str] = mapped_column(String(16), default="active")

    institute: Mapped[Institute] = relationship(back_populates="members")


class InstituteSeat(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "institute_seats"

    institute_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutes.id", ondelete="CASCADE"), index=True)
    subscription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True)
    status: Mapped[SeatStatus] = mapped_column(
        str_enum(SeatStatus, "seat_status"), default=SeatStatus.PURCHASED, index=True
    )

    institute: Mapped[Institute] = relationship(back_populates="seats")
    assignment: Mapped["InstituteAssignment | None"] = relationship(back_populates="seat", uselist=False)


class InstituteAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "institute_assignments"

    institute_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutes.id", ondelete="CASCADE"), index=True)
    candidate_email: Mapped[str] = mapped_column(String(320), index=True)
    student_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    seat_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("institute_seats.id", ondelete="SET NULL"), index=True)
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[AssignmentStatus] = mapped_column(
        str_enum(AssignmentStatus, "assignment_status"), default=AssignmentStatus.INVITED, index=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    released_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    note: Mapped[str] = mapped_column(Text, default="")

    institute: Mapped[Institute] = relationship(back_populates="assignments")
    seat: Mapped[InstituteSeat | None] = relationship(back_populates="assignment")
    invites: Mapped[list["InstituteInvite"]] = relationship(back_populates="assignment")


class InstituteInvite(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "institute_invites"

    assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institute_assignments.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    assignment: Mapped[InstituteAssignment] = relationship(back_populates="invites")
