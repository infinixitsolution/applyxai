import uuid
from typing import Literal

from pydantic import BaseModel, Field

from backend.app.services.automation_service import MAX_BATCH_EVENTS


class StartRunIn(BaseModel):
    # Fill in every form but stop before pressing Submit (the engine's stop_before_submit).
    dry_run: bool = False
    resume_mode: Literal["default", "tailor_if_gate"] = Field(
        default="default",
        description="default = upload default resume; tailor_if_gate = AI-tailor per job when JD matches.",
    )


class PairIn(BaseModel):
    code: str = Field(min_length=8, max_length=20)
    name: str = Field(default="", max_length=100)
    platform: str = Field(default="", max_length=50)
    agent_version: str = Field(default="", max_length=32)


class ConnectStartIn(BaseModel):
    name: str = Field(default="", max_length=100)
    platform: str = Field(default="", max_length=50)
    agent_version: str = Field(default="", max_length=32)


class ConnectPollIn(BaseModel):
    session_id: uuid.UUID
    secret: str = Field(min_length=16, max_length=128)


class ConnectApproveIn(BaseModel):
    session_id: uuid.UUID


class PollIn(BaseModel):
    active_run_id: uuid.UUID | None = None
    platform: str = Field(default="", max_length=50)
    agent_version: str = Field(default="", max_length=32)


class EventBatchIn(BaseModel):
    first_seq: int = Field(ge=1)
    events: list[dict] = Field(default_factory=list, max_length=MAX_BATCH_EVENTS)


class AgentAiAnswerIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    question_type: str = Field(default="text", max_length=32)
    options: list[str] = Field(default_factory=list, max_length=80)
    job_description: str = Field(default="", max_length=12000)
    job_title: str = Field(default="", max_length=300)
    company: str = Field(default="", max_length=300)


class AgentTailorIn(BaseModel):
    job_description: str = Field(min_length=1, max_length=12000)
    job_title: str = Field(default="", max_length=300)
    company: str = Field(default="", max_length=300)
