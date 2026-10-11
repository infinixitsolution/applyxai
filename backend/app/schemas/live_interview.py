import uuid

from pydantic import BaseModel, Field


class SupportMessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class LiveInterviewStartIn(BaseModel):
    token: str = Field(min_length=8, max_length=16)
    application_id: uuid.UUID | None = None


class LiveInterviewApplicationIn(BaseModel):
    application_id: uuid.UUID
