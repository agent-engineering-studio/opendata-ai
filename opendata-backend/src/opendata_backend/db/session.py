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

from .url import needs_pooler_safe_engine, to_async_dsn

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

    Accepts any common Postgres DSN form (`postgresql://`, `postgresql+asyncpg://`,
    `postgresql+psycopg://`). SSL-related query params (`sslmode`,
    `channel_binding`) are translated into asyncpg `connect_args`.
    """
    async_url, connect_args = to_async_dsn(database_url)
    # Transaction-mode poolers (Neon, Supabase) reuse the same backend
    # connection across transactions, so per-connection prepared statements
    # leak between sessions and asyncpg's DEALLOCATE storm crashes the
    # pooler. Disabling asyncpg's statement cache makes every execute a
    # plain SQL call — required for PgBouncer-style transaction pooling.
    if needs_pooler_safe_engine(database_url):
        connect_args["statement_cache_size"] = 0
    engine_kwargs: dict = {
        "echo": echo,
        "future": True,
        "pool_pre_ping": True,
        "connect_args": connect_args,
    }
    engine = create_async_engine(async_url, **engine_kwargs)
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
