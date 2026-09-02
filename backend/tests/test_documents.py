from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import Document
from app.storage import document_storage_key

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
MAX_PDF_BYTES = 10 * 1024 * 1024


async def _login(client: AsyncClient, email: str, password: str) -> None:
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": password}
    )


async def _seed_users_and_documents() -> tuple[UUID, UUID, UUID, UUID]:
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    async with engine.begin() as conn:
        user_a = (await conn.execute(text("""
                    INSERT INTO users (id, email, password_hash)
                    VALUES (gen_random_uuid(), 'doc-a@example.com', 'x')
                    RETURNING id
                    """))).scalar_one()
        user_b = (await conn.execute(text("""
                    INSERT INTO users (id, email, password_hash)
                    VALUES (gen_random_uuid(), 'doc-b@example.com', 'x')
                    RETURNING id
                    """))).scalar_one()
        doc_a_id = uuid4()
        doc_b_id = uuid4()
        doc_a = (
            await conn.execute(
                text("""
                    INSERT INTO documents (
                        id, user_id, original_filename, content_type, byte_size,
                        storage_key, status
                    )
                    VALUES (
                        :id, :uid, 'harbor-a.pdf', 'application/pdf', 128,
                        :key, 'completed'
                    )
                    RETURNING id
                    """),
                {
                    "id": doc_a_id,
                    "uid": user_a,
                    "key": document_storage_key(user_a, doc_a_id),
                },
            )
        ).scalar_one()
        doc_b = (
            await conn.execute(
                text("""
                    INSERT INTO documents (
                        id, user_id, original_filename, content_type, byte_size,
                        storage_key, status
                    )
                    VALUES (
                        :id, :uid, 'harbor-b.pdf', 'application/pdf', 128,
                        :key, 'completed'
                    )
                    RETURNING id
                    """),
                {
                    "id": doc_b_id,
                    "uid": user_b,
                    "key": document_storage_key(user_b, doc_b_id),
                },
            )
        ).scalar_one()
    await engine.dispose()
    return user_a, user_b, doc_a, doc_b


async def test_unauthenticated_upload_is_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/documents",
        files={"files": ("policy.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_list_documents_omits_other_users_rows(client: AsyncClient) -> None:
    _, _, doc_a, doc_b = await _seed_users_and_documents()
    await _login(client, "viewer@example.com", "correct-horse")
    response = await client.get("/api/v1/documents")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(doc_a) not in ids
    assert str(doc_b) not in ids


async def test_user_cannot_fetch_another_users_document(client: AsyncClient) -> None:
    _, _, _, doc_b = await _seed_users_and_documents()
    await _login(client, "viewer@example.com", "correct-horse")
    response = await client.get(f"/api/v1/documents/{doc_b}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_user_cannot_download_another_users_document(client: AsyncClient) -> None:
    _, _, _, doc_b = await _seed_users_and_documents()
    await _login(client, "viewer@example.com", "correct-horse")
    response = await client.get(f"/api/v1/documents/{doc_b}/file")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_non_pdf_is_rejected(client: AsyncClient) -> None:
    await _login(client, "owner@example.com", "correct-horse")
    response = await client.post(
        "/api/v1/documents",
        files={"files": ("notes.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


async def test_oversize_pdf_is_rejected(client: AsyncClient) -> None:
    await _login(client, "owner@example.com", "correct-horse")
    oversized = b"%PDF-1.4\n" + (b"x" * MAX_PDF_BYTES)
    response = await client.post(
        "/api/v1/documents",
        files={"files": ("huge.pdf", oversized, "application/pdf")},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


async def test_upload_pdf_returns_202_and_file_is_downloadable(
    client: AsyncClient,
) -> None:
    await _login(client, "owner@example.com", "correct-horse")
    response = await client.post(
        "/api/v1/documents",
        files={"files": ("harbor.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert response.status_code == 202
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["original_filename"] == "harbor.pdf"
    assert items[0]["status"] == "pending"
    document_id = items[0]["id"]

    listed = await client.get("/api/v1/documents")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == document_id

    fetched = await client.get(f"/api/v1/documents/{document_id}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "pending"

    download = await client.get(f"/api/v1/documents/{document_id}/file")
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF")
    assert download.headers["content-type"].startswith("application/pdf")


async def test_mixed_valid_and_invalid_files_store_nothing(
    client: AsyncClient, app
) -> None:
    await _login(client, "owner@example.com", "correct-horse")
    response = await client.post(
        "/api/v1/documents",
        files=[
            ("files", ("ok.pdf", MINIMAL_PDF, "application/pdf")),
            ("files", ("notes.txt", b"not a pdf", "text/plain")),
        ],
    )
    assert response.status_code == 415
    listed = await client.get("/api/v1/documents")
    assert listed.json()["items"] == []
    assert app.state.document_store._objects == {}


async def test_enqueue_failure_marks_document_failed(client: AsyncClient) -> None:
    from unittest.mock import patch

    await _login(client, "owner@example.com", "correct-horse")
    with patch(
        "app.routers.documents.extract_document.send",
        side_effect=ConnectionError("redis down"),
    ):
        response = await client.post(
            "/api/v1/documents",
            files={"files": ("harbor.pdf", MINIMAL_PDF, "application/pdf")},
        )
    assert response.status_code == 202
    item = response.json()["items"][0]
    assert item["status"] == "failed"
    assert item["error_code"] == "EXTRACTION_FAILED"
    assert "queued" in item["error_message"].lower()

    fetched = await client.get(f"/api/v1/documents/{item['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "failed"


async def test_download_missing_object_is_404(client: AsyncClient, app) -> None:
    await _login(client, "owner@example.com", "correct-horse")
    response = await client.post(
        "/api/v1/documents",
        files={"files": ("harbor.pdf", MINIMAL_PDF, "application/pdf")},
    )
    document_id = response.json()["items"][0]["id"]
    user_id = response.json()["items"][0]["user_id"]
    key = document_storage_key(user_id, document_id)
    del app.state.document_store._objects[key]
    download = await client.get(f"/api/v1/documents/{document_id}/file")
    assert download.status_code == 404
    assert download.json()["error"]["code"] == "NOT_FOUND"


async def test_rls_hides_other_documents_without_application_filter(
    client: AsyncClient,
) -> None:
    user_a, user_b, _, _ = await _seed_users_and_documents()
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user_a)},
        )
        rows = (await session.execute(text("SELECT user_id FROM documents"))).all()
        assert {row[0] for row in rows} == {user_a}

    async with factory() as session:
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user_b)},
        )
        result = await session.execute(text("SELECT original_filename FROM documents"))
        assert [row[0] for row in result] == ["harbor-b.pdf"]

    await engine.dispose()
    assert client


async def test_rls_errors_on_documents_without_user_setting(
    client: AsyncClient,
) -> None:
    await _seed_users_and_documents()
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        try:
            await session.execute(text("SELECT * FROM documents"))
            raised = False
        except DBAPIError:
            raised = True
    await engine.dispose()
    assert raised
    assert client


assert Document.__tablename__ == "documents"
