"""Importing this package registers every model on `Base.metadata` (Alembic relies on it)."""

from backend.app.models.base import Base
from backend.app.models.enums import ApplicationStatus, AutomationStatus, SubscriptionStatus, TokenPurpose
from backend.app.models.user import User, UserProfile
from backend.app.models.auth_token import AuthToken
from backend.app.models.preferences import ApplicationPreferences, SearchConfig
from backend.app.models.resume import Resume
from backend.app.models.job import Job
from backend.app.models.automation import AutomationJob
from backend.app.models.application import Application
from backend.app.models.subscription import Plan, Subscription
from backend.app.models.usage import UsageCounter

__all__ = [
    "Base",
    "ApplicationStatus", "AutomationStatus", "SubscriptionStatus", "TokenPurpose",
    "User", "UserProfile", "AuthToken", "SearchConfig", "ApplicationPreferences", "Resume", "Job", "AutomationJob",
    "Application", "Plan", "Subscription", "UsageCounter",
]
