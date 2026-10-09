from pydantic import BaseModel, EmailStr, Field


class InviteIn(BaseModel):
    email: EmailStr
    note: str = Field(default="", max_length=500)


class InstituteProfileIn(BaseModel):
    name: str | None = Field(default=None, max_length=190)
    contact_name: str | None = Field(default=None, max_length=190)
    phone: str | None = Field(default=None, max_length=32)
    institute_type: str | None = Field(default=None, max_length=32)
    gstin: str | None = Field(default=None, max_length=15)
    pan_number: str | None = Field(default=None, max_length=10)


class InstituteSettingsIn(BaseModel):
    timezone: str | None = None
    notify_invites: bool | None = None
    notify_acceptances: bool | None = None
    notify_low_seats: bool | None = None
    low_seat_threshold: int | None = Field(default=None, ge=1, le=50)
    invite_expiry_days: int | None = Field(default=None, ge=1, le=30)
    invite_note: str | None = Field(default=None, max_length=500)


class TokenIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class StatusIn(BaseModel):
    status: str = Field(min_length=3, max_length=32)


class PasswordIn(BaseModel):
    password: str = Field(min_length=10, max_length=128)
