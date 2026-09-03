from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Property


async def list_for_user(session: AsyncSession, user_id: UUID) -> list[Property]:
    result = await session.execute(
        select(Property)
        .where(Property.user_id == user_id)
        .order_by(Property.created_at)
    )
    return list(result.scalars().all())


async def get_for_user(
    session: AsyncSession, property_id: UUID, user_id: UUID
) -> Property | None:
    result = await session.execute(
        select(Property).where(Property.id == property_id, Property.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def add(session: AsyncSession, prop: Property) -> Property:
    session.add(prop)
    await session.flush()
    return prop


async def delete(session: AsyncSession, prop: Property) -> None:
    await session.delete(prop)


async def ids_owned_by_user(
    session: AsyncSession, user_id: UUID, property_ids: list[UUID]
) -> set[UUID]:
    if not property_ids:
        return set()
    result = await session.execute(
        select(Property.id).where(
            Property.id.in_(property_ids),
            Property.user_id == user_id,
        )
    )
    return set(result.scalars().all())
