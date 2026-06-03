"""Async SQLAlchemy engine + session factory.

A single `Database` instance is created at app startup (lifespan) and torn
down at shutdown. Routers consume `AsyncSession` via the `get_db_session`
FastAPI dependency.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

SessionFactory = async_sessionmaker[AsyncSession]


@dataclass
class Database:
    engine: AsyncEngine
    sessionmaker: SessionFactory

    async def dispose(self) -> None:
        await self.engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessionmaker() as s:
            yield s


def create_database(database_url: str, *, echo: bool = False) -> Database:
    """Build an `AsyncEngine` + `async_sessionmaker` from a connection URL.

    The URL must use the asyncpg driver, e.g.
        postgresql+asyncpg://user:pass@host:5432/db
    """
    if not database_url.startswith("postgresql+asyncpg://"):
        raise ValueError(
            "DATABASE_URL must use the postgresql+asyncpg driver "
            f"(got {database_url.split(':', 1)[0]!r})"
        )
    engine = create_async_engine(database_url, echo=echo, future=True, pool_pre_ping=True)
    return Database(
        engine=engine,
        sessionmaker=async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession),
    )


# Set by `main.lifespan` so router-level `Depends` can fetch it.
_factory: SessionFactory | None = None


def set_session_factory(factory: SessionFactory | None) -> None:
    global _factory
    _factory = factory


def get_session_factory() -> SessionFactory:
    if _factory is None:
        raise RuntimeError("Database not initialised — lifespan must call set_session_factory()")
    return _factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session
