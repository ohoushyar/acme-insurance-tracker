from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import dramatiq
import structlog
from sqlalchemy import select

from app.config import get_settings
from app.db import create_engine, create_session_factory, set_tenant
from app.models import Document
from app.queue.broker import broker
from app.storage import StorageKeyError, assert_owned_storage_key, build_document_store

log = structlog.get_logger("extraction")

_ = broker

MAX_RETRIES = 3
EXTRACT_TIME_LIMIT_MS = 10 * 60 * 1000


class NonRetryableExtractionError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _is_last_retry() -> bool:
    from dramatiq.middleware import CurrentMessage

    try:
        message = CurrentMessage.get_current_message()
    except RuntimeError:
        return True
    if message is None:
        return True
    retries = int(message.options.get("retries", 0))
    return retries >= MAX_RETRIES


async def _persist_status(
    document_id: str,
    user_id: str,
    *,
    status: str,
    extracted: dict | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            await set_tenant(session, user_id)
            result = await session.execute(
                select(Document).where(Document.id == UUID(document_id))
            )
            doc = result.scalar_one_or_none()
            if doc is None:
                return
            doc.status = status
            doc.extracted = extracted
            doc.error_code = error_code
            doc.error_message = error_message
            doc.updated_at = datetime.now(UTC)
            await session.commit()
    finally:
        await engine.dispose()


async def _run_extraction_job(document_id: str, user_id: str) -> None:
    from langchain_openrouter import ChatOpenRouter

    from app.extraction.graph import run_extraction

    settings = get_settings()
    store = build_document_store(settings)
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            await set_tenant(session, user_id)
            result = await session.execute(
                select(Document).where(Document.id == UUID(document_id))
            )
            doc = result.scalar_one_or_none()
            if doc is None:
                log.info(
                    "extraction_skipped_missing",
                    document_id=document_id,
                    user_id=user_id,
                )
                return
            try:
                assert_owned_storage_key(user_id, doc.storage_key)
            except StorageKeyError as exc:
                raise NonRetryableExtractionError(
                    "Document storage path is invalid."
                ) from exc
            storage_key = doc.storage_key
            doc.status = "processing"
            doc.updated_at = datetime.now(UTC)
            await session.commit()
    finally:
        await engine.dispose()

    log.info(
        "extraction_started",
        document_id=document_id,
        user_id=user_id,
        model=settings.openrouter_model,
    )

    try:
        pdf_bytes = await store.get_pdf(storage_key)
    except FileNotFoundError as exc:
        raise NonRetryableExtractionError(
            "The uploaded file could not be found."
        ) from exc

    if not settings.openrouter_api_key:
        raise NonRetryableExtractionError("Extraction is not configured.")

    llm = ChatOpenRouter(
        model=settings.openrouter_model,
        api_key=settings.openrouter_api_key,
        temperature=0,
        app_title="Insurance Tracker",
    )
    outcome = await run_extraction(pdf_bytes=pdf_bytes, llm=llm)
    extracted = (
        outcome.extracted.model_dump(mode="json")
        if outcome.extracted is not None
        else None
    )
    await _persist_status(
        document_id,
        user_id,
        status=outcome.status,
        extracted=extracted,
        error_code=outcome.error_code,
        error_message=outcome.error_message,
    )
    log.info(
        "extraction_finished",
        document_id=document_id,
        user_id=user_id,
        status=outcome.status,
        model=settings.openrouter_model,
    )
    if outcome.status == "failed" and outcome.error_code == "EXTRACTION_FAILED":
        return


async def _extract_document(document_id: str, user_id: str) -> None:
    try:
        await _run_extraction_job(document_id, user_id)
    except NonRetryableExtractionError as exc:
        await _persist_status(
            document_id,
            user_id,
            status="failed",
            error_code="EXTRACTION_FAILED",
            error_message=exc.message,
        )
        log.info(
            "extraction_finished",
            document_id=document_id,
            user_id=user_id,
            status="failed",
        )
    except Exception:
        log.exception(
            "extraction_error",
            document_id=document_id,
            user_id=user_id,
        )
        if _is_last_retry():
            await _persist_status(
                document_id,
                user_id,
                status="failed",
                error_code="EXTRACTION_FAILED",
                error_message="Extraction failed. Try uploading the document again.",
            )
            return
        raise


@dramatiq.actor(
    max_retries=MAX_RETRIES,
    min_backoff=15_000,
    max_backoff=60_000,
    time_limit=EXTRACT_TIME_LIMIT_MS,
)
def extract_document(document_id: str, user_id: str) -> None:
    asyncio.run(_extract_document(document_id, user_id))
