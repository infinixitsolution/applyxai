from pydantic import BaseModel, EmailStr, Field, field_validator

from backend.app.schemas.auth import _check_password


class UserUpdateIn(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None


class GrantPlanIn(BaseModel):
    plan: str = Field(min_length=1, max_length=32)
    months: int = Field(ge=1, le=24)
    note: str = Field(default="", max_length=500)


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

    _password = field_validator("password")(_check_password)

    @field_validator("organization", "contact_name", "phone")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class PartnerUpdateIn(BaseModel):
    organization: str = Field(min_length=1, max_length=190)
    contact_name: str = Field(default="", max_length=190)
    phone: str = Field(default="", max_length=32)

    @field_validator("organization", "contact_name", "phone")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class PlanUpdateIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price_cents: int = Field(ge=0, le=100_000_000)
    applications_per_month: int = Field(ge=0, le=1_000_000)
    resumes: int = Field(ge=0, le=100)
    seats: int | None = Field(default=None, ge=1, le=10_000)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=1000)
