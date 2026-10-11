import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from backend.app.models import ApplicationStatus


class PublishedContactOut(BaseModel):
    """Contact info the company published on the job posting (not the applicant)."""

    name: str = ""
    email: str = ""
    phone: str = ""
    role: str = ""
    link: str = ""


class JobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: str
    external_id: str
    title: str
    company: str
    location: str
    job_url: str
    work_setting: str
    employment_type: str
    experience_level: str
    salary_min: int | None
    salary_max: int | None
    discovered_at: datetime
    published_contacts: list[PublishedContactOut] = []

    @field_validator("published_contacts", mode="before")
    @classmethod
    def _null_contacts(cls, value):
        return value or []


class JobDetail(JobSummary):
    description: str


class ResumeVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    filename: str
    file_type: str
    created_at: datetime
    is_default: bool = False
    generated_by: str | None = None
    job_title: str | None = None
    company: str | None = None
    match_score: int | None = None
    fit_score: int | None = None


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ApplicationStatus
    applied_at: datetime | None
    failure_reason: str
    resume_id: uuid.UUID | None
    automation_job_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    job: JobSummary
    resume: ResumeVersionOut | None = None
    generated_resumes: list[ResumeVersionOut] = []


class ApplicationDetail(ApplicationOut):
    job: JobDetail


class ApplicationBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ApplicationStatus
    applied_at: datetime | None


class JobWithApplication(JobSummary):
    application: ApplicationBrief


class JobDetailWithApplication(JobDetail):
    application: ApplicationBrief


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    title: str
    body: str
    link: str
    read_at: datetime | None
    created_at: datetime


class NotificationPrefTypeIn(BaseModel):
    email: bool


class NotificationPreferencesIn(BaseModel):
    types: dict[str, NotificationPrefTypeIn]
