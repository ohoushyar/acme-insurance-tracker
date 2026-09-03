from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.extraction.schema import ConfirmExtractedPolicy
from app.models import Document
from app.policy_mapping import document_to_out
from app.queue.actors import extract_document
from app.repositories import documents as documents_repo
from app.repositories import policies as policies_repo
from app.repositories import transactions
from app.schemas import DocumentList, DocumentOut
from app.services import policies as policy_service
from app.storage import document_storage_key

if TYPE_CHECKING:
    from app.storage import DocumentStore


class ReadableUpload(Protocol):
    filename: str | None
    content_type: str | None

    async def read(self, size: int = -1) -> bytes: ...


log = structlog.get_logger("documents")

MAX_PDF_BYTES = 10 * 1024 * 1024
PDF_MAGIC = b"%PDF"


def _validate_pdf(content_type: str | None, body: bytes) -> None:
    if len(body) > MAX_PDF_BYTES:
        raise AppError(
            413,
            "PAYLOAD_TOO_LARGE",
            "PDFs must be 10 MB or smaller.",
        )
    normalized = (content_type or "").split(";")[0].strip().lower()
    if normalized != "application/pdf" or not body.startswith(PDF_MAGIC):
        raise AppError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "Upload a PDF file.",
        )


async def _require_owned(
    session: AsyncSession, user_id: UUID, document_id: UUID
) -> Document:
    document = await documents_repo.get_for_user(session, document_id, user_id)
    if document is None:
        raise AppError(404, "NOT_FOUND", "Document not found.")
    return document


async def _with_policy_ids(
    session: AsyncSession, user_id: UUID, documents: list[Document]
) -> list[DocumentOut]:
    policy_ids = await policies_repo.ids_by_source_document_ids(
        session, user_id, [item.id for item in documents]
    )
    return [document_to_out(item, policy_ids.get(item.id)) for item in documents]


async def list_documents(session: AsyncSession, user_id: UUID) -> DocumentList:
    documents = await documents_repo.list_for_user(session, user_id)
    return DocumentList(items=await _with_policy_ids(session, user_id, documents))


async def get_document(
    session: AsyncSession, user_id: UUID, document_id: UUID
) -> DocumentOut:
    document = await _require_owned(session, user_id, document_id)
    items = await _with_policy_ids(session, user_id, [document])
    return items[0]


async def download(
    session: AsyncSession,
    store: DocumentStore,
    user_id: UUID,
    document_id: UUID,
) -> tuple[Document, bytes]:
    document = await _require_owned(session, user_id, document_id)
    try:
        body = await store.get_pdf(document.storage_key)
    except FileNotFoundError as exc:
        raise AppError(404, "NOT_FOUND", "Document not found.") from exc
    return document, body


async def upload(
    session: AsyncSession,
    store: DocumentStore,
    user_id: UUID,
    files: list[ReadableUpload],
) -> DocumentList:
    if not files:
        raise AppError(422, "VALIDATION_ERROR", "Choose one or more PDF files.")

    validated: list[tuple[str, bytes]] = []
    for upload in files:
        body = await upload.read()
        _validate_pdf(upload.content_type, body)
        validated.append((upload.filename or "upload.pdf", body))

    created: list[Document] = []
    for original_filename, body in validated:
        document_id = uuid4()
        storage_key = document_storage_key(user_id, document_id)
        await store.put_pdf(storage_key, body)
        created.append(
            Document(
                id=document_id,
                user_id=user_id,
                original_filename=original_filename,
                content_type="application/pdf",
                byte_size=len(body),
                storage_key=storage_key,
                status="pending",
            )
        )

    await documents_repo.add_all(session, created)
    await transactions.commit(session)
    queued_failed = False
    for document in created:
        try:
            await asyncio.to_thread(
                extract_document.send, str(document.id), str(user_id)
            )
        except Exception:
            log.exception(
                "enqueue_failed",
                document_id=str(document.id),
                user_id=str(user_id),
            )
            queued_failed = True
            documents_repo.persist_outcome(
                document,
                status="failed",
                error_code="EXTRACTION_FAILED",
                error_message=(
                    "The extraction job could not be queued. Try uploading again."
                ),
            )
    if queued_failed:
        await transactions.commit_with_tenant(session, user_id)
    return DocumentList(items=[document_to_out(document) for document in created])


async def confirm(
    session: AsyncSession,
    user_id: UUID,
    document_id: UUID,
    extracted: ConfirmExtractedPolicy,
) -> DocumentOut:
    document = await _require_owned(session, user_id, document_id)
    if document.status in {"pending", "processing"}:
        raise AppError(409, "CONFLICT", "This document is still extracting.")
    if document.status == "failed":
        raise AppError(409, "CONFLICT", "Extraction failed — upload again.")
    if document.status not in {"completed", "reviewed"} or document.extracted is None:
        raise AppError(409, "CONFLICT", "This document is not ready to confirm.")
    documents_repo.persist_outcome(
        document,
        status="reviewed",
        extracted=extracted.model_dump(mode="json"),
    )
    policy = await policy_service.upsert_from_extracted(
        session, user_id, document, extracted
    )
    return document_to_out(document, policy.id)
