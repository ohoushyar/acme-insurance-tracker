"""Wait until ADMIN_DATABASE_URL accepts SQL (not just TCP)."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

import asyncpg
from sqlalchemy.engine.url import URL, make_url


def wait_for_postgres(admin_url: str, timeout_seconds: int) -> bool:
    if not admin_url or timeout_seconds < 1:
        return False
    url = make_url(admin_url)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            asyncio.run(_select_one(url))
            return True
        except (TimeoutError, OSError, asyncpg.PostgresError):
            time.sleep(1)
    return False


async def _select_one(url: URL) -> None:
    conn = await asyncpg.connect(
        host=url.host or "127.0.0.1",
        port=int(url.port or 5432),
        user=url.username or "postgres",
        password=url.password or "",
        database=url.database or "postgres",
        timeout=2,
    )
    try:
        await conn.execute("SELECT 1")
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timeout", type=int, nargs="?", default=90)
    args = parser.parse_args()
    admin_url = os.environ.get("ADMIN_DATABASE_URL", "")
    if not wait_for_postgres(admin_url, args.timeout):
        sys.exit(1)


if __name__ == "__main__":
    main()
