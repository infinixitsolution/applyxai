from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


def _strip_pasted_secret(value: str) -> str:
    key = (value or "").strip()
    if len(key) >= 2 and key[0] == key[-1] and key[0] in "'\"":
        key = key[1:-1].strip()
    return key


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


class SeoPageIn(BaseModel):
    title: str = Field(max_length=200)
    description: str = Field(max_length=500)
    noindex: bool = False


class SeoIn(BaseModel):
    site_url: str = Field(min_length=8, max_length=512)
    default_title: str = Field(min_length=1, max_length=200)
    title_suffix: str = Field(max_length=80)
    default_description: str = Field(min_length=1, max_length=500)
    default_keywords: str = Field(max_length=500)
    og_image_url: str = Field(max_length=512)
    twitter_card: Literal["summary", "summary_large_image"] = "summary_large_image"
    robots_index: bool = True
    robots_disallow: list[str] = Field(default_factory=lambda: ["/app/", "/admin/", "/onboarding"], max_length=20)
    google_site_verification: str = Field(max_length=200)
    bing_site_verification: str = Field(max_length=200)
    pages: dict[str, SeoPageIn]

    @field_validator("site_url")
    @classmethod
    def _strip_site_url(cls, value: str) -> str:
        v = value.strip()
        return v.rstrip("/") if v.startswith("http") else v

    @field_validator("og_image_url")
    @classmethod
    def _strip_og_url(cls, value: str) -> str:
        return value.strip()


SEO_PAGE_KEYS = ("home", "login", "register", "privacy", "terms", "refund")


class CmsIn(BaseModel):
    branding: BrandingIn
    banner: BannerIn
    landing: LandingIn
    legal: LegalIn
    seo: SeoIn

    @field_validator("seo")
    @classmethod
    def _seo_pages_complete(cls, seo: SeoIn) -> SeoIn:
        missing = [k for k in SEO_PAGE_KEYS if k not in seo.pages]
        if missing:
            raise ValueError(f"SEO pages missing keys: {', '.join(missing)}")
        return seo


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


class AuthEmailTemplateIn(BaseModel):
    subject: str = Field(max_length=500)
    body: str = Field(max_length=50_000)
    html: str = Field(default="", max_length=100_000)


class EventTemplateIn(BaseModel):
    in_app_title: str = Field(max_length=500)
    in_app_body: str = Field(max_length=10_000)
    email_subject: str = Field(max_length=500)
    email_body: str = Field(max_length=50_000)
    email_html: str = Field(default="", max_length=100_000)


class EmailTemplatesIn(BaseModel):
    auth: dict[str, AuthEmailTemplateIn]
    events: dict[str, EventTemplateIn]


class AiFeaturesIn(BaseModel):
    applications: bool = True
    resume: bool = True
    mock_interview: bool = True
    profile_sync: bool = True
    outreach: bool = True


class MockInterviewPresenterIn(BaseModel):
    mode: Literal["digital_human_3d", "static_photo", "live_stream"] = "digital_human_3d"
    image_url: str = Field(default="/mock-interviewer-host.jpg", max_length=512)
    glb_url: str = Field(default="/portrait", max_length=512)
    live_stream_url: str = Field(default="", max_length=1024)
    supports_barge_in: bool = True
    supports_replay: bool = True


class MockInterviewVoiceIn(BaseModel):
    provider: Literal["elevenlabs", "openai"] = "elevenlabs"
    elevenlabs_agent_id: str = Field(default="fA4eSDsx5xNZ1RV7zEu5", max_length=64)
    elevenlabs_model_id: str = Field(default="eleven_multilingual_v2", max_length=64)


class ElevenLabsTestIn(BaseModel):
    elevenlabs_api_key: str = ""  # empty = use saved key or .env

    @field_validator("elevenlabs_api_key")
    @classmethod
    def _normalize_elevenlabs_key(cls, value: str) -> str:
        return _strip_pasted_secret(value)


class AiModelsIn(BaseModel):
    fast: str = Field(min_length=1, max_length=120)
    strong: str = Field(min_length=1, max_length=120)
    embedding: str = Field(min_length=1, max_length=120)


class JobSourcesIn(BaseModel):
    linkedin: bool = True
    naukri: bool = False

    @model_validator(mode="after")
    def at_least_one(self):
        if not self.linkedin and not self.naukri:
            raise ValueError("Turn on at least one job source.")
        return self

    def enabled_names(self) -> list[str]:
        names = []
        if self.linkedin:
            names.append("linkedin")
        if self.naukri:
            names.append("naukri")
        return names


class LiveInterviewSettingsIn(BaseModel):
    enabled: bool = False
    display_name: str = Field(min_length=1, max_length=80)
    price_cents: int = Field(ge=100, le=10_000_000)


class OutreachCampaignIn(BaseModel):
    keywords: list[str] = Field(default_factory=lambda: ["IT training institute"], max_length=50)
    cities: list[str] = Field(default_factory=lambda: ["Bangalore"], max_length=50)
    sources: list[str] = Field(default_factory=lambda: ["google"])
    max_results: int = Field(default=10, ge=1, le=50)
    public_listing_attestation: bool = False
    send_interval_min_sec: int = Field(default=60, ge=30, le=600)
    send_interval_max_sec: int = Field(default=120, ge=30, le=900)

    @field_validator("keywords", "cities")
    @classmethod
    def _strip_lines(cls, value: list[str]) -> list[str]:
        cleaned = [line.strip() for line in value if line and line.strip()]
        return cleaned

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

    @model_validator(mode="after")
    def _intervals(self) -> "OutreachCampaignIn":
        if self.send_interval_max_sec < self.send_interval_min_sec:
            raise ValueError("send_interval_max_sec must be >= send_interval_min_sec")
        if not self.keywords:
            raise ValueError("Add at least one keyword.")
        if not self.cities:
            raise ValueError("Add at least one city.")
        return self


class OutreachSettingsIn(BaseModel):
    firecrawl_api_key: str = ""  # empty = keep existing
    campaign: OutreachCampaignIn | None = None
    whatsapp_provider: Literal["bridge", "cloud"] | None = None


class OutreachTestIn(BaseModel):
    firecrawl_api_key: str = ""  # empty = use saved key or .env


class PaymentsIn(BaseModel):
    provider: Literal["null", "razorpay", "stripe"] = "null"
    key_id: str = Field(default="", max_length=64)
    key_secret: str = ""  # empty = keep existing
    webhook_secret: str = ""  # empty = keep existing


class GstSettingsIn(BaseModel):
    enabled: bool = False
    legal_name: str = Field(default="", max_length=190)
    trade_name: str = Field(default="", max_length=190)
    address_line1: str = Field(default="", max_length=500)
    address_line2: str = Field(default="", max_length=500)
    city: str = Field(default="", max_length=120)
    state: str = Field(default="", max_length=120)
    state_code: str = Field(default="", max_length=2)
    pin: str = Field(default="", max_length=12)
    country: str = Field(default="India", max_length=80)
    gstin: str = Field(default="", max_length=15)
    pan: str = Field(default="", max_length=10)
    sac_code: str = Field(default="998313", max_length=16)
    rate_percent: float = Field(default=18.0, ge=0, le=28)
    pricing_tax_exclusive: bool = True
    invoice_prefix: str = Field(default="AXAI", max_length=20)
    invoice_next_number: int = Field(default=1, ge=1, le=9_999_999)
    invoice_footer_note: str = Field(default="", max_length=2000)


class AiIn(BaseModel):
    enabled: bool = False
    provider: Literal["openai", "openai_compatible", "gemini"] = "openai"
    base_url: str = Field(default="https://api.openai.com/v1", max_length=512)
    api_key: str = ""  # empty = keep existing
    elevenlabs_api_key: str = ""  # empty = keep existing
    models: AiModelsIn = Field(default_factory=AiModelsIn)
    features: AiFeaturesIn = Field(default_factory=AiFeaturesIn)
    mock_interview_presenter: MockInterviewPresenterIn | None = None
    mock_interview_voice: MockInterviewVoiceIn | None = None

    @field_validator("elevenlabs_api_key")
    @classmethod
    def _normalize_elevenlabs_key(cls, value: str) -> str:
        return _strip_pasted_secret(value)

    @field_validator("base_url")
    @classmethod
    def _strip_url(cls, value: str) -> str:
        return value.rstrip("/")
