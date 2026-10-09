import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MAX_HUMAN_QUESTIONS = 80
MAX_PATTERN = 500
MAX_ANSWER = 2000
MAX_USER_INFO = 20_000


class HumanQuestionIn(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    match: Literal["contains", "exact"] = "contains"
    pattern: str = Field(min_length=1, max_length=MAX_PATTERN)
    answer: str = Field(min_length=1, max_length=MAX_ANSWER)
    field_types: list[str] = Field(default_factory=list, max_length=8)
    locked: bool = False

    @field_validator("field_types")
    @classmethod
    def _types(cls, value: list[str]) -> list[str]:
        allowed = {"text", "textarea", "select", "radio", "checkbox"}
        return [t for t in value if t in allowed]


class AiPolicyIn(BaseModel):
    deny_label_contains: list[str] = Field(default_factory=lambda: ["gender", "race", "ethnicity", "disability", "veteran", "sexual"], max_length=30)

    @field_validator("deny_label_contains")
    @classmethod
    def _labels(cls, value: list[str]) -> list[str]:
        return [v.strip().lower()[:64] for v in value if v.strip()]


class PendingFormQuestionOut(BaseModel):
    id: str
    label: str
    question_type: str = "text"
    options: list[str] = Field(default_factory=list, max_length=50)
    job_id: str = ""
    job_title: str = ""
    company: str = ""
    needs_answer: bool = True


class ResolvePendingQuestionsIn(BaseModel):
    answers: list[dict] = Field(default_factory=list, max_length=50)


class ApplicationPreferencesPatch(BaseModel):
    """Flat engine keys plus optional QA fields; unknown keys rejected at service layer."""

    model_config = {"extra": "allow"}


DEFAULT_DENY = ["gender", "race", "ethnicity", "disability", "veteran", "sexual"]
