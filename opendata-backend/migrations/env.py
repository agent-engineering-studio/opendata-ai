"""Alembic environment — uses opendata-backend's SQLAlchemy metadata.

The database URL is resolved from the `DATABASE_URL` environment variable so
the same migration can run in CI, in Docker, and against a local dev
Postgres without editing alembic.ini.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from opendata_backend.db.models import Base
from opendata_backend.db.url import to_sync_dsn

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Force a sync (psycopg3) DSN for Alembic even when the runtime app uses asyncpg.
# psycopg3 understands `sslmode=require` / `channel_binding=require` natively,
# so the URL passed by Neon-style providers works as-is.
_RUNTIME_URL = os.environ.get("DATABASE_URL", "")
if _RUNTIME_URL:
    config.set_main_option("sqlalchemy.url", to_sync_dsn(_RUNTIME_URL))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema="opendata",
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # Alembic's own version-table lives in `opendata.alembic_version`, so the
        # schema must exist before `_ensure_version_table()` runs. Postgres only.
        if connection.dialect.name == "postgresql":
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS opendata"))
            connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema="opendata",
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
