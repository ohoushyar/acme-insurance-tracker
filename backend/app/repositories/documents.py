from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document


async def list_for_user(session: AsyncSession, user_id: UUID) -> list[Document]:
    result = await session.execute(
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


async def get_for_user(
    session: AsyncSession, document_id: UUID, user_id: UUID
) -> Document | None:
    result = await session.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def add(session: AsyncSession, document: Document) -> Document:
    session.add(document)
    await session.flush()
    return document


async def add_all(session: AsyncSession, documents: list[Document]) -> None:
    for document in documents:
        session.add(document)
    await session.flush()


def mark_processing(document: Document) -> None:
    document.status = "processing"
    document.updated_at = datetime.now(UTC)


def persist_outcome(
    document: Document,
    *,
    status: str,
    extracted: dict[str, Any] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    document.status = status
    document.extracted = extracted
    document.error_code = error_code
    document.error_message = error_message
    document.updated_at = datetime.now(UTC)
