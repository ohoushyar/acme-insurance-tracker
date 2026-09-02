import os

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://app:app@localhost:5432/insurance_test",
)
os.environ.setdefault(
    "ADMIN_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/insurance_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("SESSION_TTL_SECONDS", "604800")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")
os.environ.setdefault("LOG_LEVEL", "error")

from app.config import get_settings
from app.db import apply_schema
from app.main import close_runtime, create_app, init_runtime

get_settings.cache_clear()


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def redis_client() -> Redis:
    settings = get_settings()
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.fixture
async def app(redis_client: Redis):
    settings = get_settings()
    admin = create_async_engine(
        settings.admin_database_url, isolation_level="AUTOCOMMIT"
    )
    async with admin.connect() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("GRANT USAGE ON SCHEMA public TO app"))
        await conn.execute(text("GRANT CREATE ON SCHEMA public TO postgres"))
    await admin.dispose()

    await apply_schema(settings.admin_database_url)

    application = create_app()
    await init_runtime(application)
    yield application
    await close_runtime(application)


@pytest.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
