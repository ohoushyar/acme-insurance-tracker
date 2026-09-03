from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import set_tenant
from app.deps import get_current_user, get_tenant_db
from app.errors import AppError
from app.extraction.schema import ConfirmExtractedPolicy
from app.models import Document
from app.queue.actors import extract_document
from app.schemas import DocumentList, DocumentOut, UserOut
from app.storage import DocumentStore, document_storage_key

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
log = structlog.get_logger("documents")

MAX_PDF_BYTES = 10 * 1024 * 1024
PDF_MAGIC = b"%PDF"


def get_document_store(request: Request) -> DocumentStore:
    return request.app.state.document_store


def _validate_pdf(upload: UploadFile, body: bytes) -> None:
    if len(body) > MAX_PDF_BYTES:
        raise AppError(
            413,
            "PAYLOAD_TOO_LARGE",
            "PDFs must be 10 MB or smaller.",
        )
    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    if content_type != "application/pdf" or not body.startswith(PDF_MAGIC):
        raise AppError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "Upload a PDF file.",
        )


@router.post("", response_model=DocumentList, status_code=202)
async def upload_documents(
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
    store: Annotated[DocumentStore, Depends(get_document_store)],
    files: Annotated[list[UploadFile], File()],
) -> DocumentList:
    if not files:
        raise AppError(422, "VALIDATION_ERROR", "Choose one or more PDF files.")

    validated: list[tuple[str, bytes]] = []
    for upload in files:
        body = await upload.read()
        _validate_pdf(upload, body)
        validated.append((upload.filename or "upload.pdf", body))

    created: list[Document] = []
    for original_filename, body in validated:
        document_id = uuid4()
        storage_key = document_storage_key(user.id, document_id)
        await store.put_pdf(storage_key, body)
        document = Document(
            id=document_id,
            user_id=user.id,
            original_filename=original_filename,
            content_type="application/pdf",
            byte_size=len(body),
            storage_key=storage_key,
            status="pending",
        )
        session.add(document)
        created.append(document)

    await session.flush()
    await session.commit()
    queued_failed = False
    for document in created:
        try:
            await asyncio.to_thread(
                extract_document.send, str(document.id), str(user.id)
            )
        except Exception:
            log.exception(
                "enqueue_failed",
                document_id=str(document.id),
                user_id=str(user.id),
            )
            queued_failed = True
            document.status = "failed"
            document.error_code = "EXTRACTION_FAILED"
            document.error_message = (
                "The extraction job could not be queued. Try uploading again."
            )
            document.updated_at = datetime.now(UTC)
    if queued_failed:
        await set_tenant(session, str(user.id))
        await session.commit()
    payload = [DocumentOut.model_validate(document) for document in created]
    return DocumentList(items=payload)


@router.get("", response_model=DocumentList)
async def list_documents(
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> DocumentList:
    result = await session.execute(
        select(Document)
        .where(Document.user_id == user.id)
        .order_by(Document.created_at.desc())
    )
    return DocumentList(items=list(result.scalars().all()))


async def _get_owned_document(
    document_id: UUID,
    user: UserOut,
    session: AsyncSession,
) -> Document:
    result = await session.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user.id)
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise AppError(404, "NOT_FOUND", "Document not found.")
    return document


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: UUID,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> Document:
    return await _get_owned_document(document_id, user, session)


@router.get("/{document_id}/file")
async def download_document(
    document_id: UUID,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
    store: Annotated[DocumentStore, Depends(get_document_store)],
) -> Response:
    document = await _get_owned_document(document_id, user, session)
    try:
        body = await store.get_pdf(document.storage_key)
    except FileNotFoundError as exc:
        raise AppError(404, "NOT_FOUND", "Document not found.") from exc
    filename = (document.original_filename or "policy.pdf").replace('"', "")
    return Response(
        content=body,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.post("/{document_id}/confirm", response_model=DocumentOut)
async def confirm_document(
    document_id: UUID,
    extracted: ConfirmExtractedPolicy,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> Document:
    document = await _get_owned_document(document_id, user, session)
    if document.status in {"pending", "processing"}:
        raise AppError(409, "CONFLICT", "This document is still extracting.")
    if document.status == "failed":
        raise AppError(409, "CONFLICT", "Extraction failed — upload again.")
    if document.status not in {"completed", "reviewed"} or document.extracted is None:
        raise AppError(409, "CONFLICT", "This document is not ready to confirm.")
    document.extracted = extracted.model_dump(mode="json")
    document.status = "reviewed"
    document.updated_at = datetime.now(UTC)
    return document
