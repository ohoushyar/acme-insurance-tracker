from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.models import Policy, Reminder
from app.reminders import due_thresholds, utc_today
from app.repositories import policies as policies_repo
from app.repositories import reminders as reminders_repo
from app.repositories import transactions
from app.schemas import ReminderList, ReminderOut


def _to_out(reminder: Reminder, policy: Policy | None) -> ReminderOut:
    return ReminderOut(
        id=reminder.id,
        policy_id=reminder.policy_id,
        threshold_days=reminder.threshold_days,
        renewal_date=reminder.renewal_date,
        read_at=reminder.read_at,
        named_insured=policy.named_insured if policy is not None else None,
        coverage_type=policy.coverage_type if policy is not None else None,
    )


async def _policy_map(
    session: AsyncSession, user_id: UUID, reminders: list[Reminder]
) -> dict[UUID, Policy]:
    policies = await policies_repo.list_for_user(session, user_id)
    wanted = {item.policy_id for item in reminders}
    return {policy.id: policy for policy in policies if policy.id in wanted}


async def sync_due_rows(session: AsyncSession, user_id: UUID, today: date) -> None:
    policies = await policies_repo.list_for_user(session, user_id)
    existing = await reminders_repo.list_for_user(session, user_id)
    seen = {
        (item.policy_id, item.threshold_days, item.renewal_date) for item in existing
    }
    for policy in policies:
        if policy.renewal_date is None:
            continue
        for threshold in due_thresholds(policy.renewal_date, today):
            key = (policy.id, threshold, policy.renewal_date)
            if key in seen:
                continue
            await reminders_repo.insert_if_missing(
                session,
                Reminder(
                    user_id=user_id,
                    policy_id=policy.id,
                    threshold_days=threshold,
                    renewal_date=policy.renewal_date,
                ),
            )
            seen.add(key)
    await transactions.flush(session)


async def list_reminders(session: AsyncSession, user_id: UUID) -> ReminderList:
    await sync_due_rows(session, user_id, utc_today())
    items = await reminders_repo.list_for_user(session, user_id)
    policies = await _policy_map(session, user_id, items)
    return ReminderList(
        items=[_to_out(item, policies.get(item.policy_id)) for item in items],
        unread_count=sum(1 for item in items if item.read_at is None),
    )


async def mark_read(
    session: AsyncSession, user_id: UUID, reminder_id: UUID
) -> ReminderOut:
    reminder = await _owned(session, user_id, reminder_id)
    if reminder.read_at is None:
        reminder.read_at = datetime.now(UTC)
        await transactions.flush(session)
    policy = await policies_repo.get_for_user(session, reminder.policy_id, user_id)
    return _to_out(reminder, policy)


async def mark_unread(
    session: AsyncSession, user_id: UUID, reminder_id: UUID
) -> ReminderOut:
    reminder = await _owned(session, user_id, reminder_id)
    if reminder.read_at is not None:
        reminder.read_at = None
        await transactions.flush(session)
    policy = await policies_repo.get_for_user(session, reminder.policy_id, user_id)
    return _to_out(reminder, policy)


async def _owned(session: AsyncSession, user_id: UUID, reminder_id: UUID) -> Reminder:
    reminder = await reminders_repo.get_for_user(session, reminder_id, user_id)
    if reminder is None:
        raise AppError(404, "NOT_FOUND", "Reminder not found.")
    return reminder
