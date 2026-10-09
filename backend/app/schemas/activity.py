import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.app.models import ApplicationStatus


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
