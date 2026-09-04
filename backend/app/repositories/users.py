from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class DuplicateEmailError(Exception):
    pass


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create(session: AsyncSession, email: str, password_hash: str) -> User:
    user = User(email=email, password_hash=password_hash)
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise DuplicateEmailError from exc
    await session.refresh(user)
    return user


async def list_verified(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User)
        .where(User.email_verified_at.is_not(None))
        .order_by(User.created_at)
    )
    return list(result.scalars().all())


async def set_password_hash(
    session: AsyncSession, user: User, password_hash: str
) -> None:
    user.password_hash = password_hash
    await session.flush()


async def mark_email_verified(session: AsyncSession, user: User) -> None:
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC)
        await session.flush()
