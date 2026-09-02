from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, get_settings
from app.db import set_tenant
from app.errors import AppError
from app.schemas import UserOut
from app.sessions import load_session


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.session_factory


async def get_db(
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> UserOut:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise AppError(401, "UNAUTHENTICATED", "Please sign in.")
    payload = await load_session(redis, token)
    if payload is None:
        raise AppError(401, "UNAUTHENTICATED", "Please sign in.")
    return UserOut(
        id=UUID(payload["user_id"]),
        email=payload["email"],
        created_at=datetime.fromisoformat(payload["created_at"]),
    )


async def get_tenant_db(
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AsyncSession:
    await set_tenant(session, str(user.id))
    return session
