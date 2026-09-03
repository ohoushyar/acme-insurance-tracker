import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.users import DuplicateEmailError, create, get_by_email
from app.security import hash_password


async def test_create_then_get_by_email(db_session: AsyncSession) -> None:
    created = await create(
        db_session, "owner@example.com", hash_password("correct-horse")
    )
    found = await get_by_email(db_session, "owner@example.com")
    assert found is not None
    assert found.id == created.id
    assert found.email == "owner@example.com"


async def test_get_by_email_returns_none_when_missing(
    db_session: AsyncSession,
) -> None:
    assert await get_by_email(db_session, "missing@example.com") is None


async def test_create_duplicate_email_raises(db_session: AsyncSession) -> None:
    await create(db_session, "owner@example.com", hash_password("correct-horse"))
    with pytest.raises(DuplicateEmailError):
        await create(db_session, "owner@example.com", hash_password("other-horse"))
