import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.extraction.schema import (
    ConfirmExtractedPolicy,
    ExtractedPolicy,
    OptionalStr,
    StrictMoneyAmount,
)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Credentials(BaseModel):
    email: str
    password: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if not EMAIL_RE.match(email):
            raise ValueError("must be a valid email address")
        return email


class ChangePassword(BaseModel):
    current_password: str = Field(min_length=8)
    new_password: str = Field(min_length=8)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    created_at: datetime


class PropertyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    label: str
    address: str | None = None
    stated_value: Decimal | None = None
    created_at: datetime
    updated_at: datetime
    policy_ids: list[uuid.UUID] = Field(default_factory=list)


class PropertyCreate(BaseModel):
    label: str
    address: OptionalStr = None
    stated_value: StrictMoneyAmount = None

    @field_validator("label")
    @classmethod
    def require_label(cls, value: str) -> str:
        label = value.strip()
        if not label:
            raise ValueError("must not be empty")
        return label


class PropertyPatch(BaseModel):
    label: str | None = None
    address: OptionalStr = None
    stated_value: StrictMoneyAmount = None

    @field_validator("label")
    @classmethod
    def require_label_when_set(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("must not be empty")
        label = value.strip()
        if not label:
            raise ValueError("must not be empty")
        return label


class PropertyList(BaseModel):
    items: list[PropertyOut]


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    original_filename: str
    content_type: str
    byte_size: int
    status: str
    extracted: dict[str, Any] | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    policy_id: uuid.UUID | None = None


class DocumentList(BaseModel):
    items: list[DocumentOut]


class LinkSuggestion(BaseModel):
    policy_id: uuid.UUID
    label: str


class PolicyOut(ExtractedPolicy):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    source_document_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    property_ids: list[uuid.UUID] = Field(default_factory=list)
    series_id: uuid.UUID | None = None
    previous_premium: Decimal | None = None
    yoy_change_pct: float | None = None
    yoy_flagged: bool = False
    link_suggestions: list[LinkSuggestion] = Field(default_factory=list)


class PolicyLinkRequest(BaseModel):
    peer_policy_id: uuid.UUID


class PolicyHistoryPoint(BaseModel):
    year: int
    premium: Decimal | None
    policy_id: uuid.UUID


class PolicyHistory(BaseModel):
    items: list[PolicyHistoryPoint]


class PolicyPatch(ConfirmExtractedPolicy):
    property_ids: list[uuid.UUID] | None = None

    @field_validator("property_ids")
    @classmethod
    def require_property_ids_list(
        cls, value: list[uuid.UUID] | None
    ) -> list[uuid.UUID]:
        if value is None:
            raise ValueError("must be a list of property ids")
        return value


class PolicyList(BaseModel):
    items: list[PolicyOut]


class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    policy_id: uuid.UUID
    threshold_days: int
    renewal_date: date
    read_at: datetime | None = None
    named_insured: str | None = None
    coverage_type: str | None = None


class ReminderList(BaseModel):
    items: list[ReminderOut]
    unread_count: int
