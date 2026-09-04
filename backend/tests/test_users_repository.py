import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.users import (
    DuplicateEmailError,
    create,
    get_by_email,
    get_by_id,
    list_verified,
    mark_email_verified,
    set_password_hash,
)
from app.security import hash_password, verify_password


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


async def test_get_by_id_returns_created_user(db_session: AsyncSession) -> None:
    created = await create(
        db_session, "owner@example.com", hash_password("correct-horse")
    )
    found = await get_by_id(db_session, created.id)
    assert found is not None
    assert found.id == created.id
    assert found.email == "owner@example.com"


async def test_set_password_hash_updates_stored_hash(
    db_session: AsyncSession,
) -> None:
    created = await create(
        db_session, "owner@example.com", hash_password("correct-horse")
    )
    await set_password_hash(db_session, created, hash_password("new-horse-1"))
    found = await get_by_id(db_session, created.id)
    assert found is not None
    assert verify_password(found.password_hash, "new-horse-1")
    assert not verify_password(found.password_hash, "correct-horse")


async def test_list_verified_excludes_unverified(db_session: AsyncSession) -> None:
    unverified = await create(
        db_session, "unverified@example.com", hash_password("correct-horse")
    )
    verified = await create(
        db_session, "verified@example.com", hash_password("correct-horse")
    )
    await mark_email_verified(db_session, verified)
    found = await list_verified(db_session)
    ids = {user.id for user in found}
    assert verified.id in ids
    assert unverified.id not in ids
