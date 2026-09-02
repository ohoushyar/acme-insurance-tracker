from argon2 import PasswordHasher
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.sessions import session_key

COOKIE = "session"


async def test_register_returns_user_and_sets_session_cookie(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": "correct-horse"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "owner@example.com"
    assert "id" in body
    assert "created_at" in body
    assert "password" not in body
    assert "password_hash" not in body
    assert COOKIE in response.cookies


async def test_register_duplicate_email_returns_409(client: AsyncClient) -> None:
    payload = {"email": "owner@example.com", "password": "correct-horse"}
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "EMAIL_TAKEN"


async def test_register_normalizes_email_case(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "Owner@Example.com", "password": "correct-horse"},
    )
    assert response.status_code == 201
    assert response.json()["email"] == "owner@example.com"


async def test_password_is_stored_as_argon2(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": "correct-horse"},
    )
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
    assert "correct-horse" not in stored
    PasswordHasher().verify(stored, "correct-horse")


async def test_login_success_sets_cookie(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": "correct-horse"},
    )
    client.cookies.clear()
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "correct-horse"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "owner@example.com"
    assert COOKIE in response.cookies


async def test_login_wrong_password_returns_401(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": "correct-horse"},
    )
    client.cookies.clear()
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_login_unknown_email_returns_same_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "correct-horse"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_me_requires_cookie(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_me_returns_current_user(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": "correct-horse"},
    )
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "owner@example.com"
    assert "password" not in response.json()


async def test_logout_deletes_redis_key_and_rejects_cookie(
    client: AsyncClient, redis_client: Redis
) -> None:
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": "correct-horse"},
    )
    token = register.cookies[COOKIE]
    assert await redis_client.exists(session_key(token)) == 1

    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    assert await redis_client.exists(session_key(token)) == 0

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 401


async def test_missing_redis_session_is_401_even_with_cookie(
    client: AsyncClient, redis_client: Redis
) -> None:
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": "correct-horse"},
    )
    token = register.cookies[COOKIE]
    await redis_client.delete(session_key(token))
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 401


async def test_validation_error_shape(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "short"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "message" in body["error"]
