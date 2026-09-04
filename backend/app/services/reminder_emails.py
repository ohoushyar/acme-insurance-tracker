from datetime import UTC, datetime
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import set_tenant
from app.queue.email import send_reminder_email
from app.reminders import utc_today
from app.repositories import reminders as reminders_repo
from app.repositories import transactions
from app.repositories import users as users_repo
from app.services.reminders import sync_due_rows

SCAN_LOCK_KEY = "reminder_scan:lock"
SCAN_NEXT_KEY = "reminder_scan:next"
SCAN_LOCK_TTL_SECONDS = 300
SCAN_DELAY_SECONDS = 3600
REMINDER_SCAN_DELAY_MS = SCAN_DELAY_SECONDS * 1000


async def acquire_scan_lock(redis: Redis) -> bool:
    return bool(await redis.set(SCAN_LOCK_KEY, "1", nx=True, ex=SCAN_LOCK_TTL_SECONDS))


async def should_reschedule_scan(redis: Redis) -> bool:
    return bool(await redis.set(SCAN_NEXT_KEY, "1", nx=True, ex=SCAN_DELAY_SECONDS))


async def enqueue_due_digest(session: AsyncSession, user_id: UUID) -> list[UUID]:
    await set_tenant(session, str(user_id))
    await sync_due_rows(session, user_id, utc_today())
    claimed = await reminders_repo.claim_unsent(session, user_id, datetime.now(UTC))
    await transactions.flush(session)
    if not claimed:
        return []
    ids = [item.id for item in claimed]
    await transactions.commit(session)
    try:
        send_reminder_email.send(str(user_id), [str(item_id) for item_id in ids])
    except Exception:
        await set_tenant(session, str(user_id))
        await reminders_repo.clear_queued(session, user_id, ids)
        await transactions.commit(session)
        raise
    return ids


async def enqueue_due_digests_for_verified(session: AsyncSession) -> int:
    users = await users_repo.list_verified(session)
    queued = 0
    for user in users:
        await set_tenant(session, str(user.id))
        ids = await enqueue_due_digest(session, user.id)
        if ids:
            queued += 1
    return queued
