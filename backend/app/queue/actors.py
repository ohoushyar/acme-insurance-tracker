from __future__ import annotations

import asyncio
from uuid import UUID

import dramatiq
import structlog
from dramatiq.middleware.time_limit import TimeLimitExceeded

from app.config import get_settings
from app.db import create_engine, create_session_factory, set_tenant
from app.extraction.llm import (
    LLM_REQUEST_TIMEOUT_MS,
    LLM_TIMEOUT_MESSAGE,
    build_extraction_llm,
    probe_openrouter,
)
from app.queue.broker import broker
from app.repositories import documents as documents_repo
from app.storage import StorageKeyError, assert_owned_storage_key, build_document_store

log = structlog.get_logger("extraction")

_ = broker

MAX_RETRIES = 3
EXTRACT_TIME_LIMIT_MS = 3 * 60 * 1000


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
            doc = await documents_repo.get_for_user(
                session, UUID(document_id), UUID(user_id)
            )
            if doc is None:
                return
            documents_repo.persist_outcome(
                doc,
                status=status,
                extracted=extracted,
                error_code=error_code,
                error_message=error_message,
            )
            await session.commit()
    finally:
        await engine.dispose()


async def _run_extraction_job(document_id: str, user_id: str) -> None:
    from app.extraction.graph import run_extraction

    settings = get_settings()
    store = build_document_store(settings)
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            await set_tenant(session, user_id)
            doc = await documents_repo.get_for_user(
                session, UUID(document_id), UUID(user_id)
            )
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
            documents_repo.mark_processing(doc)
            await session.commit()
    finally:
        await engine.dispose()

    log.info(
        "extraction_started",
        document_id=document_id,
        user_id=user_id,
        model=settings.openrouter_model,
    )

    log.info(
        "extraction_pdf_fetch",
        document_id=document_id,
        user_id=user_id,
    )
    try:
        pdf_bytes = await store.get_pdf(storage_key)
    except FileNotFoundError as exc:
        raise NonRetryableExtractionError(
            "The uploaded file could not be found."
        ) from exc
    log.info(
        "extraction_pdf_fetched",
        document_id=document_id,
        user_id=user_id,
        byte_size=len(pdf_bytes),
    )

    if not settings.openrouter_api_key:
        raise NonRetryableExtractionError("Extraction is not configured.")

    probe_openrouter(settings)
    llm = build_extraction_llm(settings)
    log.info(
        "extraction_graph_started",
        document_id=document_id,
        user_id=user_id,
        model=settings.openrouter_model,
        timeout_ms=LLM_REQUEST_TIMEOUT_MS,
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
    try:
        asyncio.run(_extract_document(document_id, user_id))
    except TimeLimitExceeded:
        log.warning(
            "extraction_time_limit",
            document_id=document_id,
            user_id=user_id,
        )
        asyncio.run(
            _persist_status(
                document_id,
                user_id,
                status="failed",
                error_code="EXTRACTION_FAILED",
                error_message=LLM_TIMEOUT_MESSAGE,
            )
        )
