from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models import Base

PROPERTIES_RLS_STATEMENTS = [
    "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE users TO app",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE properties TO app",
    "ALTER TABLE properties ENABLE ROW LEVEL SECURITY",
    "DROP POLICY IF EXISTS properties_isolation ON properties",
    """
    CREATE POLICY properties_isolation ON properties
        USING (user_id = current_setting('app.user_id')::uuid)
        WITH CHECK (user_id = current_setting('app.user_id')::uuid)
    """,
]

DOCUMENTS_RLS_STATEMENTS = [
    "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE documents TO app",
    "ALTER TABLE documents ENABLE ROW LEVEL SECURITY",
    "DROP POLICY IF EXISTS documents_isolation ON documents",
    """
    CREATE POLICY documents_isolation ON documents
        USING (user_id = current_setting('app.user_id')::uuid)
        WITH CHECK (user_id = current_setting('app.user_id')::uuid)
    """,
]

RLS_STATEMENTS = PROPERTIES_RLS_STATEMENTS + DOCUMENTS_RLS_STATEMENTS


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def apply_schema(admin_database_url: str) -> None:
    engine = create_async_engine(admin_database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for statement in RLS_STATEMENTS:
            await conn.execute(text(statement))
    await engine.dispose()


async def set_tenant(session: AsyncSession, user_id: str) -> None:
    await session.execute(
        text("SELECT set_config('app.user_id', :uid, true)"),
        {"uid": user_id},
    )
