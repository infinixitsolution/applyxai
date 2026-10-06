from pydantic import BaseModel, Field


class CheckoutIn(BaseModel):
    plan: str = Field(min_length=1, max_length=32)


class ConfirmIn(BaseModel):
    """What the provider's checkout handed the browser. Verified server-side, never trusted as-is."""

    payment_id: str = Field(min_length=1, max_length=100)
    subscription_id: str = Field(min_length=1, max_length=100)
    signature: str = Field(min_length=1, max_length=200)
