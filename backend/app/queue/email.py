from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import dramatiq
import structlog
from redis.asyncio import Redis

from app.config import get_settings
from app.db import create_engine, create_session_factory, set_tenant
from app.email_templates import (
    reminder_digest_message,
    reset_password_message,
    verify_email_message,
)
from app.mailer import MailerError, build_mailer
from app.queue.broker import broker
from app.reminders import utc_today
from app.repositories import policies as policies_repo
from app.repositories import reminders as reminders_repo
from app.repositories import users as users_repo
from app.services.reminders import sync_due_rows

log = structlog.get_logger("email")

_ = broker

MAX_RETRIES = 3
EMAIL_TIME_LIMIT_MS = 60_000


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


async def _send_auth_email(user_id: str, kind: str, token: str) -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            user = await users_repo.get_by_id(session, UUID(user_id))
            if user is None:
                log.info("auth_email_skipped_missing", user_id=user_id, kind=kind)
                return
            if kind == "verify":
                message = verify_email_message(user, token, settings.app_public_url)
            elif kind == "reset":
                message = reset_password_message(user, token, settings.app_public_url)
            else:
                log.info("auth_email_skipped_kind", user_id=user_id, kind=kind)
                return
            await build_mailer(settings).send(message)
            log.info("auth_email_sent", user_id=user_id, kind=kind)
    finally:
        await engine.dispose()


async def _send_reminder_email(user_id: str, reminder_ids: list[str]) -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    uid = UUID(user_id)
    ids = [UUID(item) for item in reminder_ids]
    try:
        async with factory() as session:
            await set_tenant(session, user_id)
            user = await users_repo.get_by_id(session, uid)
            if user is None or user.email_verified_at is None:
                log.info("reminder_email_skipped_unverified", user_id=user_id)
                return
            if not ids:
                await sync_due_rows(session, uid, utc_today())
                claimed = await reminders_repo.claim_unsent(
                    session, uid, datetime.now(UTC)
                )
                await session.commit()
                await set_tenant(session, user_id)
                ids = [item.id for item in claimed]
            reminders = await reminders_repo.list_by_ids_for_user(session, uid, ids)
            pending = [item for item in reminders if item.emailed_at is None]
            if not pending:
                await session.commit()
                return
            policies = {
                policy.id: policy
                for policy in await policies_repo.list_for_user(session, uid)
            }
            try:
                await build_mailer(settings).send(
                    reminder_digest_message(
                        user, pending, policies, settings.app_public_url
                    )
                )
            except MailerError:
                log.info("reminder_email_failed", user_id=user_id)
                if _is_last_retry():
                    await reminders_repo.clear_queued(
                        session, uid, [item.id for item in pending]
                    )
                    await session.commit()
                    return
                await session.commit()
                raise
            await reminders_repo.mark_emailed(
                session, uid, [item.id for item in pending], datetime.now(UTC)
            )
            await session.commit()
            log.info(
                "reminder_email_sent",
                user_id=user_id,
                count=len(pending),
            )
    finally:
        await engine.dispose()


async def _scan_reminder_emails() -> None:
    from app.services import reminder_emails as reminder_email_service

    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        if not await reminder_email_service.acquire_scan_lock(redis):
            log.info("reminder_scan_skipped_lock")
            return
        try:
            async with factory() as session:
                queued = await reminder_email_service.enqueue_due_digests_for_verified(
                    session
                )
                await session.commit()
            log.info("reminder_scan_finished", queued=queued)
        except Exception:
            log.exception("reminder_scan_failed")
        if await reminder_email_service.should_reschedule_scan(redis):
            scan_reminder_emails.send_with_options(
                delay=reminder_email_service.REMINDER_SCAN_DELAY_MS
            )
    finally:
        await redis.aclose()
        await engine.dispose()


@dramatiq.actor(
    max_retries=MAX_RETRIES,
    min_backoff=15_000,
    max_backoff=60_000,
    time_limit=EMAIL_TIME_LIMIT_MS,
)
def send_auth_email(user_id: str, kind: str, token: str) -> None:
    asyncio.run(_send_auth_email(user_id, kind, token))


@dramatiq.actor(
    max_retries=MAX_RETRIES,
    min_backoff=15_000,
    max_backoff=60_000,
    time_limit=EMAIL_TIME_LIMIT_MS,
)
def send_reminder_email(user_id: str, reminder_ids: list[str]) -> None:
    asyncio.run(_send_reminder_email(user_id, reminder_ids))


@dramatiq.actor(max_retries=0, time_limit=EMAIL_TIME_LIMIT_MS)
def scan_reminder_emails() -> None:
    asyncio.run(_scan_reminder_emails())
