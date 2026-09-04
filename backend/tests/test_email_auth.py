from unittest.mock import patch
from uuid import UUID

from argon2 import PasswordHasher
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.email_tokens import (
    reset_key,
    store_reset_token,
    store_verify_token,
    verify_key,
)


async def _register(client: AsyncClient, email: str = "owner@example.com") -> None:
    with patch("app.services.auth.send_auth_email.send"):
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "correct-horse"},
        )
    assert response.status_code == 201


async def test_register_succeeds_when_verify_enqueue_fails(
    client: AsyncClient,
) -> None:
    with patch(
        "app.services.auth.send_auth_email.send",
        side_effect=RuntimeError("broker down"),
    ):
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "owner@example.com", "password": "correct-horse"},
        )
    assert response.status_code == 201
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "owner@example.com"


async def test_register_enqueues_verify_email(client: AsyncClient) -> None:
    with patch("app.services.auth.send_auth_email.send") as send:
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "owner@example.com", "password": "correct-horse"},
        )
    assert response.status_code == 201
    assert response.json()["email_verified_at"] is None
    send.assert_called_once()
    args = send.call_args.args
    assert args[1] == "verify"
    assert args[0]


async def test_register_commits_before_verify_enqueue(client: AsyncClient) -> None:
    from app.repositories import transactions

    order: list[str] = []
    real_commit = transactions.commit

    async def tracking_commit(session):
        order.append("commit")
        return await real_commit(session)

    def tracking_send(*_args, **_kwargs):
        order.append("send")

    with (
        patch("app.services.auth.transactions.commit", tracking_commit),
        patch("app.services.auth.send_auth_email.send", tracking_send),
    ):
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "owner@example.com", "password": "correct-horse"},
        )
    assert response.status_code == 201
    assert order[:2] == ["commit", "send"]


async def test_me_returns_email_verified_at_after_verify(
    client: AsyncClient, redis_client: Redis
) -> None:
    await _register(client)
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email_verified_at"] is None
    user_id = me.json()["id"]
    token = await store_verify_token(redis_client, UUID(user_id))
    with patch("app.services.auth.send_reminder_email.send"):
        verified = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verified.status_code == 200
    assert verified.json()["email_verified_at"] is not None
    me = await client.get("/api/v1/auth/me")
    assert me.json()["email_verified_at"] is not None


async def test_verify_email_commits_before_reminder_enqueue(
    client: AsyncClient, redis_client: Redis
) -> None:
    from app.repositories import transactions

    await _register(client)
    me = (await client.get("/api/v1/auth/me")).json()
    token = await store_verify_token(redis_client, UUID(me["id"]))
    order: list[str] = []
    real_commit = transactions.commit

    async def tracking_commit(session):
        order.append("commit")
        return await real_commit(session)

    def tracking_send(*_args, **_kwargs):
        order.append("send")

    with (
        patch("app.services.auth.transactions.commit", tracking_commit),
        patch("app.services.auth.send_reminder_email.send", tracking_send),
    ):
        verified = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verified.status_code == 200
    assert order[:2] == ["commit", "send"]


async def test_verify_email_rejects_bad_token(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/verify-email", json={"token": "not-a-real-token"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "TOKEN_INVALID"


async def test_forgot_password_is_204_for_unknown_and_known(
    client: AsyncClient,
) -> None:
    missing = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "missing@example.com"}
    )
    assert missing.status_code == 204
    await _register(client)
    client.cookies.clear()
    with patch("app.services.auth.send_auth_email.send") as send:
        known = await client.post(
            "/api/v1/auth/forgot-password", json={"email": "owner@example.com"}
        )
    assert known.status_code == 204
    send.assert_called_once()
    assert send.call_args.args[1] == "reset"


async def test_forgot_password_unknown_does_not_enqueue(
    client: AsyncClient,
) -> None:
    with patch("app.services.auth.send_auth_email.send") as send:
        await client.post(
            "/api/v1/auth/forgot-password", json={"email": "ghost@example.com"}
        )
    send.assert_not_called()


async def test_forgot_password_enqueue_failure_is_204(client: AsyncClient) -> None:
    await _register(client)
    client.cookies.clear()
    with patch(
        "app.services.auth.send_auth_email.send",
        side_effect=RuntimeError("broker down"),
    ):
        response = await client.post(
            "/api/v1/auth/forgot-password", json={"email": "owner@example.com"}
        )
    assert response.status_code == 204


async def test_forgot_password_cooldown_is_silent(client: AsyncClient) -> None:
    await _register(client)
    client.cookies.clear()
    with patch("app.services.auth.send_auth_email.send") as send:
        first = await client.post(
            "/api/v1/auth/forgot-password", json={"email": "owner@example.com"}
        )
        second = await client.post(
            "/api/v1/auth/forgot-password", json={"email": "owner@example.com"}
        )
    assert first.status_code == 204
    assert second.status_code == 204
    send.assert_called_once()


async def test_reset_password_updates_hash_and_verifies(
    client: AsyncClient, redis_client: Redis
) -> None:
    await _register(client)
    me = (await client.get("/api/v1/auth/me")).json()
    token = await store_reset_token(redis_client, UUID(me["id"]))
    client.cookies.clear()
    reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "new-horse-1"},
    )
    assert reset.status_code == 204
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "new-horse-1"},
    )
    assert login.status_code == 200
    assert login.json()["email_verified_at"] is not None
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    async with engine.connect() as conn:
        stored = (
            await conn.execute(
                text("SELECT password_hash FROM users WHERE email = :email"),
                {"email": "owner@example.com"},
            )
        ).scalar_one()
    await engine.dispose()
    assert stored.startswith("$argon2")
    PasswordHasher().verify(stored, "new-horse-1")
    assert not await redis_client.exists(reset_key(token))


async def test_reset_password_rejects_bad_token(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "nope", "password": "new-horse-1"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "TOKEN_INVALID"


async def test_resend_verification_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/resend-verification")
    assert response.status_code == 401


async def test_resend_verification_cooldown_is_429(client: AsyncClient) -> None:
    await _register(client)
    with patch("app.services.auth.send_auth_email.send"):
        first = await client.post("/api/v1/auth/resend-verification")
        second = await client.post("/api/v1/auth/resend-verification")
    assert first.status_code == 204
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "RATE_LIMITED"


async def test_verify_token_is_single_use(
    client: AsyncClient, redis_client: Redis
) -> None:
    await _register(client)
    me = (await client.get("/api/v1/auth/me")).json()
    token = await store_verify_token(redis_client, UUID(me["id"]))
    with patch("app.services.auth.send_reminder_email.send"):
        first = await client.post("/api/v1/auth/verify-email", json={"token": token})
        second = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert first.status_code == 200
    assert second.status_code == 400
    assert not await redis_client.exists(verify_key(token))
