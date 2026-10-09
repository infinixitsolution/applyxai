"""Status vocabularies shared by models, schemas, and services."""

import enum


class ApplicationStatus(str, enum.Enum):
    DISCOVERED = "discovered"
    QUEUED = "queued"
    RUNNING = "running"
    APPLIED = "applied"
    FAILED = "failed"
    SKIPPED = "skipped"
    EXTERNAL = "external"
    CANCELLED = "cancelled"


class AutomationStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


ACTIVE_AUTOMATION_STATUSES = (AutomationStatus.QUEUED, AutomationStatus.RUNNING, AutomationStatus.PAUSED)


class TokenPurpose(str, enum.Enum):
    VERIFY_EMAIL = "verify_email"
    RESET_PASSWORD = "reset_password"
    REFRESH = "refresh"


class SubscriptionStatus(str, enum.Enum):
    PENDING = "pending"
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PlanKind(str, enum.Enum):
    PERSONAL = "personal"
    INSTITUTE = "institute"


class InstituteStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class InstituteMemberRole(str, enum.Enum):
    ADMIN = "admin"
    STAFF = "staff"


class SeatStatus(str, enum.Enum):
    PURCHASED = "purchased"
    ASSIGNED = "assigned"
    SUSPENDED = "suspended"
    RELEASED = "released"
    EXPIRED = "expired"


class AssignmentStatus(str, enum.Enum):
    INVITED = "invited"
    PENDING_CANDIDATE_ACCEPTANCE = "pending_candidate_acceptance"
    ACTIVE = "active"
    REJECTED = "rejected"
    SUSPENDED = "suspended"
    RELEASED = "released"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


OPEN_ASSIGNMENT_STATUSES = (
    AssignmentStatus.INVITED,
    AssignmentStatus.PENDING_CANDIDATE_ACCEPTANCE,
    AssignmentStatus.ACTIVE,
)


class PartnerStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class KycStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    NOT_REQUIRED = "not_required"


class PartnerCommissionMode(str, enum.Enum):
    PERCENT_PAYMENT = "percent_payment"
    FLAT_PAYMENT = "flat_payment"
    FLAT_SEAT = "flat_seat"
    FLAT_CANDIDATE = "flat_candidate"


class CommissionStatus(str, enum.Enum):
    ACCRUED = "accrued"
    APPROVED = "approved"
    VOID = "void"


class PayoutStatus(str, enum.Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    PAID = "paid"
    REJECTED = "rejected"
