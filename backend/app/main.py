from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import Settings, get_settings
from app.db import create_engine, create_session_factory
from app.errors import register_exception_handlers
from app.logging import configure_logging
from app.routers import auth, documents, policies, properties
from app.storage import build_document_store


async def init_runtime(app: FastAPI) -> None:
    settings: Settings = app.state.settings
    engine: AsyncEngine = create_engine(settings.database_url)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    app.state.document_store = build_document_store(settings)


async def close_runtime(app: FastAPI) -> None:
    await app.state.redis.aclose()
    await app.state.engine.dispose()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_runtime(app)
    try:
        yield
    finally:
        await close_runtime(app)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="Insurance Tracker API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    register_exception_handlers(app)
    app.include_router(auth.router)
    app.include_router(properties.router)
    app.include_router(documents.router)
    app.include_router(policies.router)
    return app


app = create_app()
