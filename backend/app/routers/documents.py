from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_tenant_db
from app.extraction.schema import ConfirmExtractedPolicy
from app.schemas import DocumentList, DocumentOut, UserOut
from app.services import documents as document_service
from app.storage import DocumentStore

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


def get_document_store(request: Request) -> DocumentStore:
    return request.app.state.document_store


@router.post("", response_model=DocumentList, status_code=202)
async def upload_documents(
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
    store: Annotated[DocumentStore, Depends(get_document_store)],
    files: Annotated[list[UploadFile], File()],
) -> DocumentList:
    return await document_service.upload(session, store, user.id, files)


@router.get("", response_model=DocumentList)
async def list_documents(
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> DocumentList:
    return await document_service.list_documents(session, user.id)


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: UUID,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> DocumentOut:
    return await document_service.get_document(session, user.id, document_id)


@router.get("/{document_id}/file")
async def download_document(
    document_id: UUID,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
    store: Annotated[DocumentStore, Depends(get_document_store)],
) -> Response:
    document, body = await document_service.download(
        session, store, user.id, document_id
    )
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
) -> DocumentOut:
    return await document_service.confirm(session, user.id, document_id, extracted)
