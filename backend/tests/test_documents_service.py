from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import set_tenant
from app.errors import AppError
from app.extraction.schema import ConfirmExtractedPolicy
from app.models import Document
from app.repositories import documents as documents_repo
from app.repositories.users import create
from app.security import hash_password
from app.services import documents as document_service
from app.storage import InMemoryDocumentStore, document_storage_key
from tests.test_extraction_schema import HARBOR_COVE_EXTRACTED

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


class _FakeUpload:
    def __init__(
        self,
        filename: str,
        content_type: str,
        body: bytes,
        reads: list[str],
    ) -> None:
        self.filename = filename
        self.content_type = content_type
        self._body = body
        self._reads = reads

    async def read(self, size: int = -1) -> bytes:
        self._reads.append(self.filename)
        return self._body


async def _pending_document(session: AsyncSession, user_id) -> Document:
    document_id = uuid4()
    document = Document(
        id=document_id,
        user_id=user_id,
        original_filename="harbor.pdf",
        content_type="application/pdf",
        byte_size=128,
        storage_key=document_storage_key(user_id, document_id),
        status="pending",
    )
    await documents_repo.add(session, document)
    return document


async def test_confirm_pending_document_is_409(db_session: AsyncSession) -> None:
    owner = await create(db_session, "owner@example.com", hash_password("pw-owner1"))
    await set_tenant(db_session, str(owner.id))
    document = await _pending_document(db_session, owner.id)
    extracted = ConfirmExtractedPolicy.model_validate(HARBOR_COVE_EXTRACTED)
    with pytest.raises(AppError) as exc:
        await document_service.confirm(db_session, owner.id, document.id, extracted)
    assert exc.value.status_code == 409
    assert exc.value.code == "CONFLICT"
    assert "extracting" in exc.value.message.lower()


async def test_upload_validates_each_file_before_reading_the_next() -> None:
    reads: list[str] = []
    files = [
        _FakeUpload("notes.txt", "text/plain", b"not a pdf", reads),
        _FakeUpload("ok.pdf", "application/pdf", MINIMAL_PDF, reads),
    ]
    with pytest.raises(AppError) as exc:
        await document_service.upload(
            None,  # type: ignore[arg-type]
            InMemoryDocumentStore(),
            uuid4(),
            files,
        )
    assert exc.value.status_code == 415
    assert reads == ["notes.txt"]
