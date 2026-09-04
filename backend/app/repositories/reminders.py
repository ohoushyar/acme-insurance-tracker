from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Reminder


async def list_for_user(session: AsyncSession, user_id: UUID) -> list[Reminder]:
    result = await session.execute(
        select(Reminder)
        .where(Reminder.user_id == user_id)
        .order_by(
            Reminder.read_at.asc().nulls_first(),
            Reminder.threshold_days.asc(),
            Reminder.renewal_date.asc(),
        )
    )
    return list(result.scalars().all())


async def get_for_user(
    session: AsyncSession, reminder_id: UUID, user_id: UUID
) -> Reminder | None:
    result = await session.execute(
        select(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def add(session: AsyncSession, reminder: Reminder) -> Reminder:
    session.add(reminder)
    await session.flush()
    return reminder


async def insert_if_missing(session: AsyncSession, reminder: Reminder) -> None:
    stmt = (
        insert(Reminder)
        .values(
            id=reminder.id or uuid4(),
            user_id=reminder.user_id,
            policy_id=reminder.policy_id,
            threshold_days=reminder.threshold_days,
            renewal_date=reminder.renewal_date,
        )
        .on_conflict_do_nothing(constraint="uq_reminders_policy_threshold_renewal")
    )
    await session.execute(stmt)
