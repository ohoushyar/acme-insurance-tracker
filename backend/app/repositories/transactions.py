from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import set_tenant


async def flush(session: AsyncSession) -> None:
    await session.flush()


async def commit(session: AsyncSession) -> None:
    await session.commit()


async def commit_with_tenant(session: AsyncSession, user_id: UUID) -> None:
    await set_tenant(session, str(user_id))
    await session.commit()
