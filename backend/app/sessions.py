import hashlib
import json
import secrets
from datetime import datetime
from uuid import UUID

from redis.asyncio import Redis

from app.config import Settings


def session_key(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"session:{digest}"


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


async def store_session(
    redis: Redis,
    token: str,
    user_id: UUID,
    email: str,
    created_at: datetime,
    settings: Settings,
) -> None:
    payload = json.dumps(
        {
            "user_id": str(user_id),
            "email": email,
            "created_at": created_at.isoformat(),
        }
    )
    await redis.set(session_key(token), payload, ex=settings.session_ttl_seconds)


async def load_session(redis: Redis, token: str) -> dict[str, str] | None:
    raw = await redis.get(session_key(token))
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    data = json.loads(raw)
    return data


async def delete_session(redis: Redis, token: str) -> None:
    await redis.delete(session_key(token))
