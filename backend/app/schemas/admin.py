from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from backend.app.models.enums import KycStatus, PartnerCommissionMode, PartnerStatus
from backend.app.schemas.auth import _check_password


class UserCreateIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    first_name: str = Field(default="", max_length=100)
    last_name: str = Field(default="", max_length=100)
    is_admin: bool = False
    is_verified: bool = True

    _password = field_validator("password")(_check_password)

    @field_validator("first_name", "last_name")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class UserUpdateIn(BaseModel):
    email: EmailStr | None = None
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None
    is_admin: bool | None = None
    is_verified: bool | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class GrantPlanIn(BaseModel):
    plan: str = Field(min_length=1, max_length=32)
    months: int = Field(ge=1, le=24)
    note: str = Field(default="", max_length=500)


class TestTemplateIn(BaseModel):
    kind: str = Field(min_length=1, max_length=64)
    to: EmailStr | None = None


class BroadcastNotificationsIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(default="", max_length=5000)
    link: str = Field(default="", max_length=512)
    user_ids: list[str] = Field(min_length=1, max_length=500)


class TestEmailIn(BaseModel):
    to: EmailStr | None = None            # defaults to the admin's own address


class InstituteCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=190)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    contact_name: str = Field(default="", max_length=190)
    phone: str = Field(default="", max_length=32)
    approve: bool = True

    _password = field_validator("password")(_check_password)

    @field_validator("name", "contact_name", "phone")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class InstituteUpdateIn(BaseModel):
    name: str = Field(min_length=1, max_length=190)
    contact_name: str = Field(default="", max_length=190)
    phone: str = Field(default="", max_length=32)

    @field_validator("name", "contact_name", "phone")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class PartnerCreateIn(BaseModel):
    organization: str = Field(min_length=1, max_length=190)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    contact_name: str = Field(default="", max_length=190)
    phone: str = Field(default="", max_length=32)
    approve: bool = True
    commission_mode: PartnerCommissionMode = PartnerCommissionMode.PERCENT_PAYMENT
    commission_bps: int = Field(default=2000, ge=0, le=10_000)
    commission_flat_cents: int = Field(default=0, ge=0, le=100_000_000)

    _password = field_validator("password")(_check_password)

    @field_validator("organization", "contact_name", "phone")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _commission(self) -> "PartnerCreateIn":
        if self.commission_mode == PartnerCommissionMode.PERCENT_PAYMENT:
            return self
        if self.commission_flat_cents <= 0:
            raise ValueError("Enter a positive flat commission amount in INR.")
        return self


class PartnerUpdateIn(BaseModel):
    organization: str = Field(min_length=1, max_length=190)
    contact_name: str = Field(default="", max_length=190)
    phone: str = Field(default="", max_length=32)
    commission_mode: PartnerCommissionMode
    commission_bps: int = Field(ge=0, le=10_000)
    commission_flat_cents: int = Field(ge=0, le=100_000_000)
    status: PartnerStatus
    kyc_status: KycStatus
    gstin: str = Field(default="", max_length=15)
    pan_number: str = Field(default="", max_length=10)
    payout_account: str = Field(default="", max_length=255)
    payout_ifsc: str = Field(default="", max_length=20)
    email: EmailStr | None = None

    @field_validator("organization", "contact_name", "phone", "payout_account")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("gstin", "pan_number", "payout_ifsc")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def _commission(self) -> "PartnerUpdateIn":
        if self.commission_mode == PartnerCommissionMode.PERCENT_PAYMENT:
            return self
        if self.commission_flat_cents <= 0:
            raise ValueError("Enter a positive flat commission amount in INR.")
        return self


class PlanUpdateIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price_cents: int = Field(ge=0, le=100_000_000)
    applications_per_month: int = Field(ge=0, le=1_000_000)
    resumes: int = Field(ge=0, le=100)
    seats: int | None = Field(default=None, ge=1, le=10_000)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=1000)
