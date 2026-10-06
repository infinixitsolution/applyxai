from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import ApplicationPreferences, SearchConfig, User, UserProfile
from backend.app.schemas.profile import ProfileIn, SearchConfigIn
from backend.app.services.engine_fields import APPLICATION_FIELDS, validate_mapping

_PROFILE_FIELDS = ("phone", "headline", "summary", "current_title", "current_company", "experience_years",
                   "skills", "preferred_roles", "preferred_locations")


def get_profile(db: Session, user: User) -> dict:
    profile = user.profile
    data = {"email": user.email, "first_name": user.first_name, "last_name": user.last_name}
    for name in _PROFILE_FIELDS:
        data[name] = getattr(profile, name) if profile else None
    data["skills"] = data["skills"] or []
    data["preferred_roles"] = data["preferred_roles"] or []
    data["preferred_locations"] = data["preferred_locations"] or []
    return data


def update_profile(db: Session, user: User, payload: ProfileIn) -> dict:
    user.first_name, user.last_name = payload.first_name, payload.last_name
    if user.profile is None:
        user.profile = UserProfile(user_id=user.id)
    for name in _PROFILE_FIELDS:
        value = getattr(payload, name)
        if value is None and name != "experience_years":
            value = ""
        setattr(user.profile, name, value)
    db.commit()
    db.refresh(user)
    return get_profile(db, user)


def get_search(db: Session, user: User) -> SearchConfig | None:
    return db.scalar(select(SearchConfig).where(SearchConfig.user_id == user.id))


def update_search(db: Session, user: User, payload: SearchConfigIn) -> SearchConfig:
    config = get_search(db, user)
    if config is None:
        config = SearchConfig(user_id=user.id)
        db.add(config)
    for name, value in payload.model_dump().items():
        setattr(config, name, value)
    db.commit()
    db.refresh(config)
    return config


def get_application(db: Session, user: User) -> dict:
    prefs = db.scalar(select(ApplicationPreferences).where(ApplicationPreferences.user_id == user.id))
    return dict(prefs.answers) if prefs else {}


def update_application(db: Session, user: User, changes: dict) -> dict:
    """Merge changes into the stored answers; null removes a key (engine default applies)."""
    cleaned = validate_mapping(APPLICATION_FIELDS, changes, allow_null=True)
    prefs = db.scalar(select(ApplicationPreferences).where(ApplicationPreferences.user_id == user.id))
    if prefs is None:
        prefs = ApplicationPreferences(user_id=user.id, answers={})
        db.add(prefs)
    answers = dict(prefs.answers or {})
    for key, value in cleaned.items():
        if value is None:
            answers.pop(key, None)
        else:
            answers[key] = value
    prefs.answers = answers                     # reassign so the JSON column is marked dirty
    db.commit()
    return dict(answers)
