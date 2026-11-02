"""Per-attempt services: every agent and every grading run gets its own database and Redis index.

A slot is a pair (database <prefix>_<k>, Redis database k). Slots are leased with a PostgreSQL
advisory lock held for the whole use, so two processes (or a crashed one and its replacement) never
share a slot. The target's tests reset their own schema; the harness only creates the database.
"""

from __future__ import annotations

import asyncio
import fcntl
import os
import zlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import psycopg

from .config import load, workdir

LOCK_BASE = 734_000  # advisory-lock key space for slots


def _prefix() -> str:
    """Slot namespace: AEH_SLOT_PREFIX lets a test suite run beside a real benchmark on one server."""
    return os.environ.get("AEH_SLOT_PREFIX", "aeh_slot")


def _lock(k: int) -> int:
    return LOCK_BASE + (zlib.crc32(_prefix().encode()) % 10_000) * 100 + k


@dataclass(frozen=True)
class Slot:
    index: int
    database_url: str
    redis_url: str


def _urls(k: int) -> tuple[str, str, str]:
    s = load("harness")["services"]
    admin = s["database_admin_url"]
    db = f"{_prefix()}_{k}"
    return admin, admin.rsplit("/", 1)[0] + "/" + db, f"{s['redis_url'].rstrip('/')}/{k}"


def prepare(n: int, extensions: list[str]) -> None:
    """Create the slot databases (idempotent)."""
    for k in range(1, n + 1):
        admin, url, _ = _urls(k)
        with psycopg.connect(admin, autocommit=True) as c:
            name = url.rsplit("/", 1)[1]
            if not c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
                c.execute(f'CREATE DATABASE "{name}"')
        with psycopg.connect(url, autocommit=True) as c:
            for e in extensions:
                c.execute(f'CREATE EXTENSION IF NOT EXISTS "{e}"')


class Slots:
    def __init__(self, n: int | None = None):
        self.n = n or int(load("harness")["slots"])
        if not 1 <= self.n <= 15:
            raise ValueError("slots must be between 1 and 15 (Redis databases 1..15)")
        self._free: asyncio.Queue[int] = asyncio.Queue()
        for k in range(1, self.n + 1):
            self._free.put_nowait(k)

    @asynccontextmanager
    async def lease(self) -> AsyncIterator[Slot]:
        """A free slot. A slot another process holds is skipped and tried again later."""
        while True:
            k = await self._free.get()
            admin, url, redis = _urls(k)
            conn = await psycopg.AsyncConnection.connect(admin, autocommit=True)
            row = await (await conn.execute("SELECT pg_try_advisory_lock(%s)", (_lock(k),))).fetchone()
            if row and row[0]:
                break
            await conn.close()
            self._free.put_nowait(k)
            await asyncio.sleep(0.5)
        try:
            yield Slot(k, url, redis)
        finally:
            await conn.close()  # releases the advisory lock
            self._free.put_nowait(k)


def mypy_cache(target: str) -> Path:
    """One mypy cache per target, shared by every grading run and agent: third-party modules are
    checked once instead of in every copy of the repository."""
    p = workdir() / "mypy-cache" / target
    p.mkdir(parents=True, exist_ok=True)
    return p


@asynccontextmanager
async def locked(path: Path) -> AsyncIterator[None]:
    """An exclusive file lock across processes (mypy must not write its cache twice at once)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    f = path.open("w")
    try:
        await asyncio.to_thread(fcntl.flock, f, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()
