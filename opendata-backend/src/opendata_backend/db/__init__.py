"""Database layer — SQLAlchemy 2.x async + Alembic migrations.

`session.py` exposes the async session factory wired up by `main.lifespan`.
`models.py` holds the ORM classes that mirror the `opendata.*` schema owned
by the agent-stack submodule. `repositories/` carries query objects so
routers never touch the ORM directly.
"""

from .models import ApiKey, Base, Classification, Favorite, History, User
from .session import (
    Database,
    SessionFactory,
    create_database,
    get_session_factory,
)

__all__ = [
    "ApiKey",
    "Base",
    "Classification",
    "Database",
    "Favorite",
    "History",
    "SessionFactory",
    "User",
    "create_database",
    "get_session_factory",
]
