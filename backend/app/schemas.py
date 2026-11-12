from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .domain.comparison import InvalidAmount, parse_amount

Status = Literal["pending", "verified_match", "mismatch", "needs_review", "expired"]
Name = Annotated[str, Field(min_length=1, max_length=120)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _amount(v):
    try:
        return parse_amount(v)
    except InvalidAmount as e:
        raise ValueError(str(e)) from None


class IntentionCreate(_Strict):
    recipient_name: Name
    amount: Decimal
    purpose: Annotated[str, Field(min_length=1, max_length=200)]
    reference: Annotated[str, Field(max_length=60)] | None = None
    expires_in_minutes: int = Field(default=1440, ge=5, le=10080)

    @field_validator("amount", mode="before")
    @classmethod
    def _v(cls, v):
        return _amount(v)

    @field_validator("reference")
    @classmethod
    def _blank_ref(cls, v):
        return v or None


class IntentionOut(BaseModel):
    id: UUID
    recipient_name: str
    amount: Decimal
    currency: str = "ZAR"
    purpose: str
    reference: str | None
    status: Status
    expires_at: datetime
    created_at: datetime


class IntentionPage(BaseModel):
    items: list[IntentionOut]
    limit: int
    offset: int


class VerifyRequest(_Strict):
    intention_id: UUID
    recipient_name: Name
    amount: Decimal
    purpose: Annotated[str, Field(max_length=200)] | None = None
    reference: Annotated[str, Field(max_length=60)] | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def _v(cls, v):
        return _amount(v)


class VerifyResponse(BaseModel):
    simulated: Literal[True] = True
    intention_id: UUID
    overall_result: Literal["match", "mismatch", "needs_review"]
    recipient_match: bool
    recipient_needs_review: bool
    amount_match: bool
    purpose_match: bool | None
    explanation: list[str]
    disclaimer: str = (
        "Simulation only. A match means the details agree with your intention; "
        "it does not mean a payment is safe. A mismatch does not prove fraud."
    )


class HistoryItem(BaseModel):
    id: UUID
    intention_id: UUID
    overall_result: str
    recipient_match: bool
    amount_match: bool
    purpose_match: bool | None
    created_at: datetime
