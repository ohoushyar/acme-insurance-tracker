from uuid import UUID

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app import email_tokens
from app.errors import AppError
from app.models import User
from app.queue.email import send_auth_email, send_reminder_email
from app.repositories import transactions
from app.repositories.users import (
    DuplicateEmailError,
    create,
    get_by_email,
    get_by_id,
    mark_email_verified,
    set_password_hash,
)
from app.security import hash_password, verify_password

log = structlog.get_logger()


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


async def get_user(session: AsyncSession, user_id: UUID) -> User:
    user = await get_by_id(session, user_id)
    if user is None:
        raise AppError(401, "UNAUTHENTICATED", "Please sign in.")
    return user


async def change_password(
    session: AsyncSession, user_id: UUID, current_password: str, new_password: str
) -> None:
    user = await get_by_id(session, user_id)
    if user is None or not verify_password(user.password_hash, current_password):
        raise AppError(401, "INVALID_CREDENTIALS", "Current password is incorrect.")
    await set_password_hash(session, user, hash_password(new_password))


async def enqueue_verification(
    session: AsyncSession,
    redis: Redis,
    user_id: UUID,
    *,
    require_cooldown: bool = False,
) -> None:
    if require_cooldown and not await email_tokens.acquire_verify_cooldown(
        redis, user_id
    ):
        raise AppError(
            429, "RATE_LIMITED", "Wait a minute before requesting another email."
        )
    token = await email_tokens.store_verify_token(redis, user_id)
    await transactions.commit(session)
    send_auth_email.send(str(user_id), "verify", token)


async def verify_email(session: AsyncSession, redis: Redis, token: str) -> User:
    user_id = await email_tokens.consume_verify_token(redis, token)
    if user_id is None:
        raise AppError(400, "TOKEN_INVALID", "This verification link is not valid.")
    user = await get_by_id(session, user_id)
    if user is None:
        raise AppError(400, "TOKEN_INVALID", "This verification link is not valid.")
    await mark_email_verified(session, user)
    await transactions.commit(session)
    try:
        send_reminder_email.send(str(user.id), [])
    except Exception:  # noqa: BLE001
        log.info("reminder_email_enqueue_failed", user_id=str(user.id))
    return user


async def enqueue_password_reset(
    session: AsyncSession, redis: Redis, email: str
) -> None:
    if not await email_tokens.acquire_reset_cooldown(redis, email):
        return
    user = await get_by_email(session, email)
    if user is None:
        return
    token = await email_tokens.store_reset_token(redis, user.id)
    try:
        send_auth_email.send(str(user.id), "reset", token)
    except Exception:  # noqa: BLE001
        log.info("reset_email_enqueue_failed", user_id=str(user.id))


async def reset_password(
    session: AsyncSession, redis: Redis, token: str, new_password: str
) -> None:
    user_id = await email_tokens.consume_reset_token(redis, token)
    if user_id is None:
        raise AppError(400, "TOKEN_INVALID", "This reset link is not valid.")
    user = await get_by_id(session, user_id)
    if user is None:
        raise AppError(400, "TOKEN_INVALID", "This reset link is not valid.")
    await set_password_hash(session, user, hash_password(new_password))
    await mark_email_verified(session, user)
