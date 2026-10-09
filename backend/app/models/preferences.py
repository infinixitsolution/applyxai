import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin


class SearchConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A user's job-search preferences. Enumerated values are stored as the exact strings
    the engine clicks on LinkedIn ("Entry level", "Full-time", "Remote", ...), never as IDs;
    the API validates them against modules/validator.py before saving.
    """

    __tablename__ = "search_configs"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    keywords: Mapped[list] = mapped_column(JSONType, default=list)             # engine: search_terms
    location: Mapped[str] = mapped_column(String(255), default="")             # engine: search_location
    easy_apply_only: Mapped[bool] = mapped_column(Boolean, default=True)
    experience_level: Mapped[list] = mapped_column(JSONType, default=list)
    job_type: Mapped[list] = mapped_column(JSONType, default=list)
    on_site: Mapped[list] = mapped_column(JSONType, default=list)
    companies: Mapped[list] = mapped_column(JSONType, default=list)
    date_posted: Mapped[str] = mapped_column(String(32), default="")
    sort_by: Mapped[str] = mapped_column(String(32), default="")
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    # Remaining config_schema "search" fields (bad words, sponsorship phrases, ...).
    extra: Mapped[dict] = mapped_column(JSONType, default=dict)


class ApplicationPreferences(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Answers the engine uses to fill application forms (config_schema "personals" /
    "questions" / run settings), keyed by the engine's own setting names."""

    __tablename__ = "application_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    answers: Mapped[dict] = mapped_column(JSONType, default=dict)
    human_questions: Mapped[list] = mapped_column(JSONType, default=list)
    ai_applications_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    user_information_all: Mapped[str] = mapped_column(Text, default="")
    ai_policy: Mapped[dict] = mapped_column(JSONType, default=lambda: {"deny_label_contains": ["gender", "race", "ethnicity", "disability", "veteran", "sexual"]})
    pending_form_questions: Mapped[list] = mapped_column(JSONType, default=list)
