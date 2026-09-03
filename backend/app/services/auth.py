from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.models import User
from app.repositories.users import DuplicateEmailError, create, get_by_email
from app.security import hash_password, verify_password


async def register(session: AsyncSession, email: str, password: str) -> User:
    try:
        return await create(session, email, hash_password(password))
    except DuplicateEmailError:
        raise AppError(
            409, "EMAIL_TAKEN", "An account with this email already exists."
        ) from None


async def login(session: AsyncSession, email: str, password: str) -> User:
    user = await get_by_email(session, email)
    if user is None or not verify_password(user.password_hash, password):
        raise AppError(401, "INVALID_CREDENTIALS", "Email or password is incorrect.")
    return user
