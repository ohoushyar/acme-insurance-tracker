import importlib.util
import os
import re
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db import ensure_login_role


def test_ensure_login_role_rejects_invalid_names() -> None:
    with pytest.raises(ValueError):
        ensure_login_role(None, role="App", password="x")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ensure_login_role(None, role="app;drop", password="x")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ensure_login_role(None, role="", password="x")  # type: ignore[arg-type]


def test_wait_for_postgres_rejects_invalid_inputs() -> None:
    path = Path(__file__).resolve().parents[1] / "scripts" / "wait_for_postgres.py"
    spec = importlib.util.spec_from_file_location("wait_for_postgres", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.wait_for_postgres("", 5) is False
    assert module.wait_for_postgres("postgresql+asyncpg://x:y@localhost/db", 0) is False


async def test_ensure_login_role_creates_missing_role() -> None:
    engine = create_async_engine(os.environ["ADMIN_DATABASE_URL"])
    role = f"r{uuid4().hex[:12]}"
    assert re.fullmatch(r"[a-z][a-z0-9_]{0,62}", role)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: ensure_login_role(sync_conn, role, "s3cret")
            )
            await conn.run_sync(
                lambda sync_conn: ensure_login_role(sync_conn, role, "s3cret")
            )
            found = await conn.scalar(
                text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
                {"role": role},
            )
            assert found == 1
    finally:
        async with engine.begin() as conn:
            await conn.execute(text(f"DROP ROLE IF EXISTS {role}"))
        await engine.dispose()
