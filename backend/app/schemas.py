import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.extraction.schema import ExtractedPolicy, OptionalStr, StrictMoneyAmount

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


class PolicyOut(ExtractedPolicy):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    source_document_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class PolicyList(BaseModel):
    items: list[PolicyOut]
