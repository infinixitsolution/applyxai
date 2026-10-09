from pydantic import BaseModel, EmailStr, Field


class EnrollInstituteIn(BaseModel):
    name: str = Field(min_length=1, max_length=190)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    contact_name: str = Field(default="", max_length=190)
    phone: str = Field(default="", max_length=32)


class PartnerProfileIn(BaseModel):
    organization: str | None = Field(default=None, max_length=190)
    contact_name: str | None = Field(default=None, max_length=190)
    phone: str | None = Field(default=None, max_length=32)


class PartnerTaxIn(BaseModel):
    gstin: str | None = Field(default=None, max_length=15)
    pan_number: str | None = Field(default=None, max_length=10)
    payout_account: str | None = Field(default=None, max_length=255)
    payout_ifsc: str | None = Field(default=None, max_length=20)


class KycDocumentIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    note: str = Field(default="", max_length=255)


class CampaignIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    note: str = Field(default="", max_length=255)


class PayoutIn(BaseModel):
    amount_cents: int | None = Field(default=None, ge=1)


class StatusIn(BaseModel):
    status: str = Field(min_length=3, max_length=32)


class KycStatusIn(BaseModel):
    status: str = Field(min_length=3, max_length=32)
