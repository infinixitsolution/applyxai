import uuid

from pydantic import BaseModel, Field

from backend.app.services.automation_service import MAX_BATCH_EVENTS


class StartRunIn(BaseModel):
    # Fill in every form but stop before pressing Submit (the engine's stop_before_submit).
    dry_run: bool = False


class PairIn(BaseModel):
    code: str = Field(min_length=8, max_length=20)
    name: str = Field(default="", max_length=100)
    platform: str = Field(default="", max_length=50)
    agent_version: str = Field(default="", max_length=32)


class PollIn(BaseModel):
    active_run_id: uuid.UUID | None = None
    platform: str = Field(default="", max_length=50)
    agent_version: str = Field(default="", max_length=32)


class EventBatchIn(BaseModel):
    first_seq: int = Field(ge=1)
    events: list[dict] = Field(default_factory=list, max_length=MAX_BATCH_EVENTS)
