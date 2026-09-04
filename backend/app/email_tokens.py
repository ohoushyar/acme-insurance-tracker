from __future__ import annotations

import hashlib
import html
import secrets
from uuid import UUID

from redis.asyncio import Redis

VERIFY_TTL_SECONDS = 86400
RESET_TTL_SECONDS = 3600
COOLDOWN_TTL_SECONDS = 60


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_key(token: str) -> str:
    return f"email_verify:{_digest(token)}"


def reset_key(token: str) -> str:
    return f"password_reset:{_digest(token)}"


def verify_cooldown_key(user_id: UUID) -> str:
    return f"verify_cooldown:{user_id}"


def reset_cooldown_key(email: str) -> str:
    return f"reset_cooldown:{_digest(email)}"


def new_token() -> str:
    return secrets.token_urlsafe(32)


async def store_verify_token(redis: Redis, user_id: UUID) -> str:
    token = new_token()
    await redis.set(verify_key(token), str(user_id), ex=VERIFY_TTL_SECONDS)
    return token


async def store_reset_token(redis: Redis, user_id: UUID) -> str:
    token = new_token()
    await redis.set(reset_key(token), str(user_id), ex=RESET_TTL_SECONDS)
    return token


async def consume_verify_token(redis: Redis, token: str) -> UUID | None:
    key = verify_key(token)
    raw = await redis.getdel(key)
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return UUID(raw)


async def consume_reset_token(redis: Redis, token: str) -> UUID | None:
    key = reset_key(token)
    raw = await redis.getdel(key)
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return UUID(raw)


async def acquire_verify_cooldown(redis: Redis, user_id: UUID) -> bool:
    return bool(
        await redis.set(
            verify_cooldown_key(user_id), "1", nx=True, ex=COOLDOWN_TTL_SECONDS
        )
    )


async def acquire_reset_cooldown(redis: Redis, email: str) -> bool:
    return bool(
        await redis.set(
            reset_cooldown_key(email), "1", nx=True, ex=COOLDOWN_TTL_SECONDS
        )
    )


def escape(value: str) -> str:
    return html.escape(value, quote=True)
