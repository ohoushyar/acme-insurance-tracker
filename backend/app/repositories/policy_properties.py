from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PolicyProperty


async def property_ids_for_policies(
    session: AsyncSession, user_id: UUID, policy_ids: list[UUID]
) -> dict[UUID, list[UUID]]:
    grouped: dict[UUID, list[UUID]] = {policy_id: [] for policy_id in policy_ids}
    if not policy_ids:
        return grouped
    result = await session.execute(
        select(PolicyProperty.policy_id, PolicyProperty.property_id).where(
            PolicyProperty.policy_id.in_(policy_ids),
            PolicyProperty.user_id == user_id,
        )
    )
    for row in result:
        grouped[row.policy_id].append(row.property_id)
    return grouped


async def policy_ids_for_properties(
    session: AsyncSession, user_id: UUID, property_ids: list[UUID]
) -> dict[UUID, list[UUID]]:
    grouped: dict[UUID, list[UUID]] = {property_id: [] for property_id in property_ids}
    if not property_ids:
        return grouped
    result = await session.execute(
        select(PolicyProperty.property_id, PolicyProperty.policy_id).where(
            PolicyProperty.property_id.in_(property_ids),
            PolicyProperty.user_id == user_id,
        )
    )
    for row in result:
        grouped[row.property_id].append(row.policy_id)
    return grouped


async def replace_links(
    session: AsyncSession,
    user_id: UUID,
    policy_id: UUID,
    property_ids: list[UUID],
) -> None:
    await session.execute(
        delete(PolicyProperty).where(
            PolicyProperty.policy_id == policy_id,
            PolicyProperty.user_id == user_id,
        )
    )
    for property_id in property_ids:
        session.add(
            PolicyProperty(
                policy_id=policy_id,
                property_id=property_id,
                user_id=user_id,
            )
        )
