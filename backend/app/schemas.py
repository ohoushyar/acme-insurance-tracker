import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    created_at: datetime


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


class DocumentList(BaseModel):
    items: list[DocumentOut]
