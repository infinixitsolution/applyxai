from pydantic import BaseModel, EmailStr, Field


class UserUpdateIn(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None


class GrantPlanIn(BaseModel):
    plan: str = Field(min_length=1, max_length=32)
    months: int = Field(ge=1, le=24)
    note: str = Field(default="", max_length=500)


class TestEmailIn(BaseModel):
    to: EmailStr | None = None            # defaults to the admin's own address


class PlanUpdateIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price_cents: int = Field(ge=0, le=100_000_000)
    applications_per_month: int = Field(ge=0, le=1_000_000)
    resumes: int = Field(ge=0, le=100)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=1000)
