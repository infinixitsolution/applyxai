import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ScrapeJobCreateIn(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    location: str = Field(default="", max_length=190)
    sources: list[str] = Field(default_factory=lambda: ["google"])
    max_results: int = Field(default=25, ge=1, le=50)
    public_listing_attestation: bool = False

    @field_validator("query", "location")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("sources")
    @classmethod
    def _sources(cls, value: list[str]) -> list[str]:
        allowed = {"google", "facebook", "instagram", "linkedin"}
        cleaned = [s.strip().lower() for s in value if s.strip()]
        if not cleaned:
            return ["google"]
        bad = [s for s in cleaned if s not in allowed]
        if bad:
            raise ValueError(f"Unknown sources: {', '.join(bad)}")
        return cleaned


class LeadProfileIn(BaseModel):
    payload: dict = Field(default_factory=dict)


class LeadBulkActionIn(BaseModel):
    lead_ids: list[uuid.UUID] = Field(min_length=1, max_length=25)
    action: Literal["complete", "enhance"]


class LeadBulkImportIn(BaseModel):
    """One contact per line: email, phone, or optional name + contact (comma/pipe/tab separated)."""

    contacts: str = Field(min_length=1, max_length=500_000)
    enrich: bool = True

    @field_validator("contacts")
    @classmethod
    def _strip_contacts(cls, value: str) -> str:
        return value.strip()


class LeadChatIn(BaseModel):
    channel: str = "whatsapp"
    text: str = Field(min_length=1, max_length=4000)

    @field_validator("channel")
    @classmethod
    def _channel(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned != "whatsapp":
            raise ValueError("Only whatsapp is supported.")
        return cleaned

    @field_validator("text")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()


class WhatsappTestSendIn(BaseModel):
    phone: str = Field(min_length=8, max_length=32)
    text: str = Field(min_length=1, max_length=4000)

    @field_validator("phone", "text")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class LeadSendIn(BaseModel):
    channels: list[str] = Field(default_factory=lambda: ["email"])
    approve: bool = True

    @field_validator("channels")
    @classmethod
    def _channels(cls, value: list[str]) -> list[str]:
        allowed = {"email", "whatsapp"}
        cleaned = [c.strip().lower() for c in value if c.strip()]
        if not cleaned:
            raise ValueError("Select at least one channel.")
        bad = [c for c in cleaned if c not in allowed]
        if bad:
            raise ValueError(f"Unknown channels: {', '.join(bad)}")
        return cleaned
