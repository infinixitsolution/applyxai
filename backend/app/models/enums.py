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
