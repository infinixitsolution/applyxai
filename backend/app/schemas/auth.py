import uuid
from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

PASSWORD_MIN = 10
PASSWORD_MAX = 128   # Argon2 handles long input, but cap it so a 1 MB "password" can't burn CPU
AccountType = Literal["candidate", "institute", "partner"]


def _check_password(value: str) -> str:
    if value.strip() != value:
        raise ValueError("Password must not start or end with a space")
    if len(set(value)) < 4:
        raise ValueError("Password is too simple")
    return value


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)
    first_name: str = Field(default="", max_length=100)
    last_name: str = Field(default="", max_length=100)
    account_type: AccountType = "candidate"
    institute_name: str = Field(default="", max_length=190)
    contact_name: str = Field(default="", max_length=190)
    phone: str = Field(default="", max_length=32)
    gstin: str = Field(default="", max_length=15)
    pan_number: str = Field(default="", max_length=10)
    organization: str = Field(default="", max_length=190)
    referral_code: str = Field(default="", max_length=16)
    agreed: bool = False

    _password = field_validator("password")(_check_password)

    @field_validator("first_name", "last_name", "institute_name", "contact_name", "organization", "referral_code")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class LoginIn(BaseModel):
    # Only registration enforces strict email rules; login must work for every existing account,
    # including ones created by an admin with an internal domain such as .local.
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+$")
    password: str = Field(min_length=1, max_length=PASSWORD_MAX)


class EmailIn(BaseModel):
    email: EmailStr


class TokenIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class ResetPasswordIn(TokenIn):
    new_password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)

    _password = field_validator("new_password")(_check_password)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    is_verified: bool
    is_admin: bool
    created_at: datetime
    last_login_at: datetime | None
    workspace: Literal["app", "admin", "institute", "partner"] = "app"
    institute_id: uuid.UUID | None = None
    partner_id: uuid.UUID | None = None
    institute_status: str | None = None
    partner_status: str | None = None
