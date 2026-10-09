import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.services.resume_templates import normalize_template_id


class ResumeAiPreviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resume_id: uuid.UUID
    job_description: str = Field(min_length=40, max_length=20000)


class ResumeAiTailorIn(ResumeAiPreviewIn):
    job_id: str = Field(default="", max_length=64)
    application_id: uuid.UUID | None = None
    template_id: str | None = Field(default=None, max_length=32)

    @field_validator("template_id")
    @classmethod
    def _template(cls, v: str | None) -> str | None:
        if v is None or not str(v).strip():
            return None
        return normalize_template_id(v)


class ResumeApplyStyleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(min_length=2, max_length=32)
    application_id: uuid.UUID | None = None

    @field_validator("template_id")
    @classmethod
    def _template(cls, v: str) -> str:
        return normalize_template_id(v)


class MasterSkillsUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    master_skills: list[str] = Field(min_length=1, max_length=80)


class ResumeIntakeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    apply: bool = Field(default=True, description="When true, merge into profile and application answers.")
