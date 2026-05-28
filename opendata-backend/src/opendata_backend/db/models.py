"""SQLAlchemy ORM mirrors of the `opendata.*` schema.

These mirror the canonical migrations owned by the agent-stack submodule
(see `vendor/agent-stack/db/migrations/opendata/`). When the submodule is
not initialised we ship a stub initial migration in
`opendata-backend/migrations/versions/0001_initial.py` that creates the
same tables with the same columns and constraints declared here.

Schema is `opendata`. Tables live there explicitly to avoid colliding with
other agent-stack consumers in the same database.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# BIGINT in Postgres, INTEGER in SQLite — required because SQLite only auto-
# increments INTEGER columns. Tests run on aiosqlite.
_PK = BigInteger().with_variant(Integer(), "sqlite")


class Base(DeclarativeBase):
    metadata_kwargs: dict[str, Any] = {"schema": "opendata"}


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email", "email"),
        {"schema": "opendata"},
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    clerk_user_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    favorites: Mapped[list["Favorite"]] = relationship(back_populates="user")
    history: Mapped[list["History"]] = relationship(back_populates="user")
    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="user")


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "source", "dataset_id", name="uq_favorites_user_dataset"),
        {"schema": "opendata"},
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        _PK, ForeignKey("opendata.users.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_id: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="favorites")


class History(Base):
    __tablename__ = "history"
    __table_args__ = (
        Index("ix_history_user_created", "user_id", "created_at"),
        {"schema": "opendata"},
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        _PK, ForeignKey("opendata.users.id", ondelete="CASCADE"), nullable=False
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    response_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="history")


class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = ({"schema": "opendata"},)

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        _PK, ForeignKey("opendata.users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="api_keys")


class Classification(Base):
    __tablename__ = "classifications"
    __table_args__ = (
        UniqueConstraint(
            "source", "dataset_id", "taxonomy_hash", name="uq_classifications_dataset_taxonomy"
        ),
        {"schema": "opendata"},
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_id: Mapped[str] = mapped_column(Text, nullable=False)
    taxonomy_hash: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
