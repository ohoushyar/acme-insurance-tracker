from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Policy


async def list_for_user(session: AsyncSession, user_id: UUID) -> list[Policy]:
    result = await session.execute(
        select(Policy)
        .where(Policy.user_id == user_id)
        .order_by(Policy.renewal_date.asc().nulls_last(), Policy.created_at.desc())
    )
    return list(result.scalars().all())


async def get_for_user(
    session: AsyncSession, policy_id: UUID, user_id: UUID
) -> Policy | None:
    result = await session.execute(
        select(Policy).where(Policy.id == policy_id, Policy.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_by_source_document(
    session: AsyncSession, document_id: UUID, user_id: UUID
) -> Policy | None:
    result = await session.execute(
        select(Policy).where(
            Policy.source_document_id == document_id,
            Policy.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def add(session: AsyncSession, policy: Policy) -> Policy:
    session.add(policy)
    await session.flush()
    return policy


async def delete(session: AsyncSession, policy: Policy) -> None:
    await session.delete(policy)


async def ids_by_source_document_ids(
    session: AsyncSession, user_id: UUID, document_ids: list[UUID]
) -> dict[UUID, UUID]:
    if not document_ids:
        return {}
    result = await session.execute(
        select(Policy.source_document_id, Policy.id).where(
            Policy.source_document_id.in_(document_ids),
            Policy.user_id == user_id,
        )
    )
    return {row.source_document_id: row.id for row in result}
