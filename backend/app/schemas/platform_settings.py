from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SocialLinksIn(BaseModel):
    twitter: str = ""
    linkedin: str = ""
    github: str = ""


class BrandingIn(BaseModel):
    app_name: str = Field(min_length=1, max_length=120)
    contact_email: str = Field(min_length=3, max_length=320)
    footer_line: str = Field(max_length=500)
    social_links: SocialLinksIn = SocialLinksIn()


class BannerIn(BaseModel):
    enabled: bool = False
    message: str = Field(max_length=500)
    tone: Literal["info", "warning", "success"] = "info"


class LandingFeatureIn(BaseModel):
    icon: str = Field(max_length=32)
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=2000)


class LandingStepIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=2000)


class LandingFaqIn(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=5000)


class LandingIn(BaseModel):
    hero_badge: str = Field(max_length=200)
    hero_title: str = Field(min_length=1, max_length=300)
    hero_subtitle: str = Field(max_length=2000)
    hero_cta_primary: str = Field(max_length=80)
    hero_cta_secondary: str = Field(max_length=80)
    hero_footnote: str = Field(max_length=200)
    features_heading: str = Field(max_length=200)
    features: list[LandingFeatureIn] = Field(min_length=1, max_length=20)
    steps_heading: str = Field(max_length=200)
    steps: list[LandingStepIn] = Field(min_length=1, max_length=12)
    pricing_heading: str = Field(max_length=200)
    pricing_subtitle: str = Field(max_length=500)
    faq_heading: str = Field(max_length=200)
    faq: list[LandingFaqIn] = Field(max_length=30)
    faq_contact_line: str = Field(max_length=500)


class LegalIn(BaseModel):
    privacy_md: str = Field(max_length=100_000)
    terms_md: str = Field(max_length=100_000)
    refund_md: str = Field(max_length=100_000)


class CmsIn(BaseModel):
    branding: BrandingIn
    banner: BannerIn
    landing: LandingIn
    legal: LegalIn


class SmtpIn(BaseModel):
    enabled: bool = True
    host: str = Field(max_length=255)
    port: int = Field(ge=1, le=65535)
    username: str = Field(max_length=320)
    password: str = ""  # empty = keep existing
    from_address: str = Field(min_length=3, max_length=320)


class AuthEmailIn(BaseModel):
    require_verification: bool
    verification_hours: int = Field(ge=1, le=168)
    password_reset_minutes: int = Field(ge=5, le=1440)
    frontend_url: str = Field(min_length=8, max_length=512)

    @field_validator("frontend_url")
    @classmethod
    def _strip_slash(cls, value: str) -> str:
        return value.rstrip("/")


class NotificationTypeIn(BaseModel):
    email: bool


class NotificationsIn(BaseModel):
    types: dict[str, NotificationTypeIn]


class AiFeaturesIn(BaseModel):
    applications: bool = True
    resume: bool = True


class AiModelsIn(BaseModel):
    fast: str = Field(min_length=1, max_length=120)
    strong: str = Field(min_length=1, max_length=120)
    embedding: str = Field(min_length=1, max_length=120)


class PaymentsIn(BaseModel):
    provider: Literal["null", "razorpay"] = "null"
    key_id: str = Field(default="", max_length=64)
    key_secret: str = ""  # empty = keep existing
    webhook_secret: str = ""  # empty = keep existing


class AiIn(BaseModel):
    enabled: bool = False
    provider: Literal["openai", "openai_compatible", "gemini"] = "openai"
    base_url: str = Field(default="https://api.openai.com/v1", max_length=512)
    api_key: str = ""  # empty = keep existing
    models: AiModelsIn = Field(default_factory=AiModelsIn)
    features: AiFeaturesIn = Field(default_factory=AiFeaturesIn)

    @field_validator("base_url")
    @classmethod
    def _strip_url(cls, value: str) -> str:
        return value.rstrip("/")
