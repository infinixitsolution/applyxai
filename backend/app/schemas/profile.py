import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from automation.options import DATE_POSTED, EXPERIENCE_LEVELS, JOB_TYPES, SORT_BY, WORK_SETTINGS
from backend.app.services.engine_fields import SEARCH_EXTRA_FIELDS, FieldErrors, clean_str_list, validate_mapping

_PHONE = re.compile(r"^[0-9+()\-.\s]{4,32}$")


def _strict_list(values: list[str], allowed: list[str], label: str) -> list[str]:
    cleaned = clean_str_list(values, label=label)
    bad = [v for v in cleaned if v not in allowed]
    if bad:
        raise ValueError(f"Invalid {label} {bad}. Allowed: {', '.join(allowed)}")
    return cleaned


def _one_of(value: str, allowed: list[str], label: str) -> str:
    if value not in allowed:
        raise ValueError(f"Invalid {label} '{value}'. Allowed: {', '.join(repr(a) for a in allowed)}")
    return value


class ProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    first_name: str = Field(default="", max_length=100)
    last_name: str = Field(default="", max_length=100)
    phone: str | None = Field(default=None, max_length=32)
    headline: str | None = Field(default=None, max_length=255)
    summary: str | None = Field(default=None, max_length=5000)
    current_title: str | None = Field(default=None, max_length=255)
    current_company: str | None = Field(default=None, max_length=255)
    experience_years: int | None = Field(default=None, ge=0, le=60)
    skills: list[str] = Field(default_factory=list)
    preferred_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v):
        if not v:
            return None
        if not _PHONE.match(v):
            raise ValueError("Phone number may contain digits, spaces and + ( ) - . only")
        return v

    @field_validator("skills")
    @classmethod
    def _skills(cls, v):
        return clean_str_list(v, max_items=100, max_len=100, label="skill")

    @field_validator("preferred_roles", "preferred_locations")
    @classmethod
    def _short_lists(cls, v):
        return clean_str_list(v, max_items=20, max_len=255, label="entry")


class ProfileOut(ProfileIn):
    model_config = ConfigDict(extra="ignore")

    email: str


class SearchConfigIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    keywords: list[str]
    location: str = Field(default="", max_length=255)
    easy_apply_only: bool = True
    experience_level: list[str] = Field(default_factory=list)
    job_type: list[str] = Field(default_factory=list)
    on_site: list[str] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    date_posted: str = ""
    sort_by: str = ""
    salary_min: int | None = Field(default=None, ge=0, le=100_000_000)
    salary_max: int | None = Field(default=None, ge=0, le=100_000_000)
    extra: dict = Field(default_factory=dict)

    @field_validator("keywords")
    @classmethod
    def _keywords(cls, v):
        v = clean_str_list(v, max_items=20, max_len=200, label="keyword")
        if not v:
            raise ValueError("Add at least one job title or keyword")
        return v

    @field_validator("experience_level")
    @classmethod
    def _experience(cls, v):
        return _strict_list(v, EXPERIENCE_LEVELS, "experience level")

    @field_validator("job_type")
    @classmethod
    def _job_type(cls, v):
        return _strict_list(v, JOB_TYPES, "job type")

    @field_validator("on_site")
    @classmethod
    def _on_site(cls, v):
        return _strict_list(v, WORK_SETTINGS, "work setting")

    @field_validator("companies")
    @classmethod
    def _companies(cls, v):
        return clean_str_list(v, max_items=50, max_len=255, label="company")

    @field_validator("date_posted")
    @classmethod
    def _date_posted(cls, v):
        return _one_of(v, DATE_POSTED, "date posted")

    @field_validator("sort_by")
    @classmethod
    def _sort_by(cls, v):
        return _one_of(v, SORT_BY, "sort order")

    @field_validator("extra")
    @classmethod
    def _extra(cls, v):
        try:
            return validate_mapping(SEARCH_EXTRA_FIELDS, v)
        except FieldErrors as exc:
            raise ValueError("; ".join(f"{e['field']}: {e['message']}" for e in exc.errors)) from None

    @model_validator(mode="after")
    def _salary_range(self):
        if self.salary_min is not None and self.salary_max is not None and self.salary_min > self.salary_max:
            raise ValueError("Minimum salary cannot be greater than maximum salary")
        return self


class SearchConfigOut(SearchConfigIn):
    model_config = ConfigDict(extra="ignore")

    keywords: list[str]
    updated_at: datetime | None = None

    @field_validator("keywords")
    @classmethod
    def _keywords(cls, v):
        return v                               # stored data may predate a rule change; don't fail reads


class ResumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    filename: str
    file_type: str
    file_size: int
    is_default: bool
    created_at: datetime


class ResumeRenameIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
