"""
Collects a user's saved profile, search preferences, and application answers into the flat
{engine_setting: value} mapping that automation.run_config.build_run_config turns into a
run config. Values were validated when they were saved (services/engine_fields.py).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from automation.run_config import missing_requirements
from backend.app.models import ApplicationPreferences, Resume, SearchConfig, User, UserProfile
from backend.app.services.engine_fields import SEARCH_COLUMNS


def engine_values(db: Session, user_id: uuid.UUID) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise LookupError("user not found")
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
    values: dict = {"first_name": user.first_name, "last_name": user.last_name}

    if profile is not None:
        values["phone_number"] = profile.phone
        if profile.headline:
            values["linkedin_headline"] = profile.headline
        if profile.summary:
            values["linkedin_summary"] = profile.summary
        if profile.experience_years is not None:
            values["years_of_experience"] = str(profile.experience_years)
        if profile.current_company:
            values["recent_employer"] = profile.current_company

    search = db.scalar(select(SearchConfig).where(SearchConfig.user_id == user_id))
    if search is not None:
        values.update(search.extra or {})
        values.update({engine_key: getattr(search, column) for engine_key, column in SEARCH_COLUMNS.items()})

    prefs = db.scalar(select(ApplicationPreferences).where(ApplicationPreferences.user_id == user_id))
    if prefs is not None:
        # Explicit answers win over values derived from the profile above.
        values.update({k: v for k, v in (prefs.answers or {}).items() if v is not None})
    return values


def default_resume(db: Session, user_id: uuid.UUID) -> Resume | None:
    return db.scalar(select(Resume).where(Resume.user_id == user_id, Resume.is_default.is_(True)))


def readiness_problems(db: Session, user_id: uuid.UUID) -> list[str]:
    """Empty when the user has everything a run needs."""
    return missing_requirements(engine_values(db, user_id))
