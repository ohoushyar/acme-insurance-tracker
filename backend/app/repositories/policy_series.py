from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Policy, PolicySeries


async def get_for_user(
    session: AsyncSession, series_id: UUID, user_id: UUID
) -> PolicySeries | None:
    result = await session.execute(
        select(PolicySeries).where(
            PolicySeries.id == series_id, PolicySeries.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def add(session: AsyncSession, series: PolicySeries) -> PolicySeries:
    session.add(series)
    await session.flush()
    return series


async def delete(session: AsyncSession, series: PolicySeries) -> None:
    await session.delete(series)


async def members_for_series(
    session: AsyncSession, series_id: UUID, user_id: UUID
) -> list[Policy]:
    result = await session.execute(
        select(Policy).where(Policy.series_id == series_id, Policy.user_id == user_id)
    )
    return list(result.scalars().all())


async def member_count(session: AsyncSession, series_id: UUID, user_id: UUID) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(Policy)
        .where(Policy.series_id == series_id, Policy.user_id == user_id)
    )
    return int(result.scalar_one())


async def list_by_series_ids(
    session: AsyncSession, user_id: UUID, series_ids: list[UUID]
) -> dict[UUID, list[Policy]]:
    if not series_ids:
        return {}
    result = await session.execute(
        select(Policy).where(
            Policy.user_id == user_id, Policy.series_id.in_(series_ids)
        )
    )
    grouped: dict[UUID, list[Policy]] = {series_id: [] for series_id in series_ids}
    for policy in result.scalars().all():
        if policy.series_id is not None:
            grouped.setdefault(policy.series_id, []).append(policy)
    return grouped
