import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.services import auth as auth_service


async def test_register_then_login(db_session: AsyncSession) -> None:
    created = await auth_service.register(
        db_session, "owner@example.com", "correct-horse"
    )
    logged_in = await auth_service.login(
        db_session, "owner@example.com", "correct-horse"
    )
    assert logged_in.id == created.id
    assert logged_in.email == "owner@example.com"


async def test_register_duplicate_email_is_409(db_session: AsyncSession) -> None:
    await auth_service.register(db_session, "owner@example.com", "correct-horse")
    with pytest.raises(AppError) as exc:
        await auth_service.register(db_session, "owner@example.com", "other-horse")
    assert exc.value.status_code == 409
    assert exc.value.code == "EMAIL_TAKEN"


async def test_login_wrong_password_is_401(db_session: AsyncSession) -> None:
    await auth_service.register(db_session, "owner@example.com", "correct-horse")
    with pytest.raises(AppError) as exc:
        await auth_service.login(db_session, "owner@example.com", "wrong-password")
    assert exc.value.status_code == 401
    assert exc.value.code == "INVALID_CREDENTIALS"


async def test_login_unknown_email_is_401(db_session: AsyncSession) -> None:
    with pytest.raises(AppError) as exc:
        await auth_service.login(db_session, "missing@example.com", "correct-horse")
    assert exc.value.status_code == 401
    assert exc.value.code == "INVALID_CREDENTIALS"
