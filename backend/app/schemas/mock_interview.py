import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.models.enums import InterviewType, MockInterviewMessageRole, MockInterviewSessionStatus


class MockInterviewCreateIn(BaseModel):
    application_id: uuid.UUID
    interview_types: list[InterviewType] = Field(min_length=1, max_length=4)

    @field_validator("interview_types")
    @classmethod
    def _normalize_mixed(cls, value: list[InterviewType]) -> list[InterviewType]:
        raw = [v.value if isinstance(v, InterviewType) else str(v) for v in value]
        if InterviewType.MIXED.value in raw:
            return [InterviewType.MIXED]
        return value


class MockInterviewTurnIn(BaseModel):
    content: str = Field(min_length=1, max_length=12000)
    client_turn_id: uuid.UUID | None = None


class MockInterviewTtsIn(BaseModel):
    text: str = Field(min_length=1, max_length=4096)


class MockInterviewTtsOut(BaseModel):
    audio_base64: str = ""
    audio_mime: str = ""


class MockInterviewCompleteIn(BaseModel):
    """Optional camera snapshots (JPEG data URLs) for presentation coaching — not stored after analysis."""

    presentation_frames: list[str] = Field(default_factory=list, max_length=12)


class MockInterviewMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: MockInterviewMessageRole
    content: str
    meta: dict | None = None
    created_at: datetime


class MockInterviewSessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    interview_types: list[str]
    status: MockInterviewSessionStatus
    turn_count: int
    context_snapshot: dict
    feedback: dict | None = None
    created_at: datetime
    updated_at: datetime
    overall_score: int | None = None
    max_duration_seconds: int = 1800
    max_questions: int = 20
    ends_at: datetime
    seconds_remaining: int | None = None


class MockInterviewSessionDetail(MockInterviewSessionSummary):
    messages: list[MockInterviewMessageOut] = []


class MockInterviewTurnOut(BaseModel):
    candidate_message: MockInterviewMessageOut
    interviewer_message: MockInterviewMessageOut
    should_end: bool
    turn_count: int
    audio_base64: str = ""
    audio_mime: str = ""


class MockInterviewOpeningOut(BaseModel):
    interviewer_message: MockInterviewMessageOut
    should_end: bool
    audio_base64: str = ""
    audio_mime: str = ""


class MockInterviewFeedbackJobOut(BaseModel):
    job_id: uuid.UUID
    session_id: uuid.UUID
    operation: str
    status: str
    attempt_count: int = 0
    error_code: str | None = None
    error_message: str | None = None
    presentation_frame_count: int = 0
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class MockInterviewCompleteOut(BaseModel):
    session: MockInterviewSessionDetail | None = None
    feedback: dict | None = None
    job: MockInterviewFeedbackJobOut | None = None
