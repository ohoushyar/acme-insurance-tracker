from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.storage import document_storage_key


async def _insert_pending_document(user_id: str) -> str:
    settings = get_settings()
    document_id = uuid4()
    engine = create_async_engine(settings.admin_database_url)
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO documents (
                    id, user_id, original_filename, content_type, byte_size,
                    storage_key, status
                )
                VALUES (
                    :id, :uid, 'harbor.pdf', 'application/pdf', 64,
                    :key, 'pending'
                )
                """),
            {
                "id": document_id,
                "uid": user_id,
                "key": document_storage_key(user_id, document_id),
            },
        )
    await engine.dispose()
    return str(document_id)


async def _document_status(document_id: str) -> str:
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    async with engine.connect() as conn:
        status = (
            await conn.execute(
                text("SELECT status FROM documents WHERE id = :id"),
                {"id": document_id},
            )
        ).scalar_one()
    await engine.dispose()
    return status


async def test_extract_document_actor_leaves_terminal_status(
    client: AsyncClient,
) -> None:
    from app.queue.actors import extract_document
    from dramatiq import Worker
    from dramatiq.brokers.stub import StubBroker

    await client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": "correct-horse"},
    )
    me = (await client.get("/api/v1/auth/me")).json()
    document_id = await _insert_pending_document(me["id"])

    broker = StubBroker()
    broker.emit_after("process_boot")
    extract_document.broker = broker
    broker.declare_actor(extract_document)

    extract_document.send(document_id, me["id"])
    worker = Worker(broker, worker_timeout=100)
    worker.start()
    try:
        broker.join(extract_document.queue_name, timeout=5000)
    finally:
        worker.stop()

    status = await _document_status(document_id)
    assert status in {"completed", "failed"}
