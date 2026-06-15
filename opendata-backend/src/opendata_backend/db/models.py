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
    Numeric,
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


class OcProgetto(Base):
    """Local mirror of the OpenCoesione bulk dataset (progetti_esteso CSV).

    One row per (project, comune): discovery on the real tracciato showed
    COD_COMUNE is MULTI-VALUED (':::'-joined — a project can insist on several
    comuni), so the spec's `clp unique` becomes `(clp, cod_comune)` unique and
    the ingest explodes the localisation. Per-comune aggregations stay correct
    (each project appears once per comune, full amounts — same convention as
    the OpenCoesione territorial navigation); cross-comune sums would double
    count multi-comune projects, so the query tools are comune-scoped.

    Codes are normalised to ISTAT form at ingest: cod_comune 6-digit
    ('072006'), cod_provincia 3-digit ('072'), cod_regione without leading
    zeros ('16'). `tema`/`natura`/`stato` carry the CSV labels verbatim.
    `raw` keeps the full 202-column record for audit on the FIRST comune row
    of each project only (it would otherwise be duplicated per comune).
    """

    __tablename__ = "oc_progetti"
    __table_args__ = (
        UniqueConstraint("clp", "cod_comune", name="uq_oc_progetti_clp_comune"),
        Index("ix_oc_progetti_comune_tema_ciclo", "cod_comune", "tema", "ciclo"),
        Index("ix_oc_progetti_provincia", "cod_provincia"),
        Index("ix_oc_progetti_regione", "cod_regione"),
        {"schema": "opendata"},
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    clp: Mapped[str] = mapped_column(Text, nullable=False)
    # '' (not NULL) when the project has no comune-level localisation, so the
    # (clp, cod_comune) unique constraint still bites (NULLs compare distinct).
    cod_comune: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cod_provincia: Mapped[str | None] = mapped_column(Text, nullable=True)
    cod_regione: Mapped[str | None] = mapped_column(Text, nullable=True)
    tema: Mapped[str | None] = mapped_column(Text, nullable=True)
    ciclo: Mapped[str | None] = mapped_column(Text, nullable=True)
    natura: Mapped[str | None] = mapped_column(Text, nullable=True)
    stato: Mapped[str | None] = mapped_column(Text, nullable=True)
    finanziamento_totale: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    pagamenti: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    titolo: Mapped[str | None] = mapped_column(Text, nullable=True)
    soggetto_attuatore: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ComuneAnagrafica(Base):
    """Anagrafica comuni con popolazione — base del peer group (spec 08).

    Popolata da `opendata-comuni-sync` (dataset comuni-json, dati ISTAT,
    censimento 2011 — per la fascia 0.5×–2× la stalenza è irrilevante e i
    criteri sono sempre dichiarati negli output). Niente geometria (R4).
    """

    __tablename__ = "comuni_anagrafica"
    __table_args__ = (
        Index("ix_comuni_anagrafica_regione", "cod_regione"),
        {"schema": "opendata"},
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    cod_comune: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    cod_provincia: Mapped[str | None] = mapped_column(Text, nullable=True)
    cod_regione: Mapped[str | None] = mapped_column(Text, nullable=True)
    popolazione: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


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


class ComuneKnowledge(Base):
    """Versione della "conoscenza" per comune (F1/F2).

    Incrementata quando cambiano i documenti del comune nel KG (upload/delete,
    F2). Entra nella chiave della cache analisi: bumpare la versione invalida
    tutte le schede in cache di quel comune (rigenerate al prossimo accesso).
    In F1 resta a 0 (nessun documento ancora), ma la colonna c'è già.
    """

    __tablename__ = "comune_knowledge"
    __table_args__ = ({"schema": "opendata"},)

    cod_comune: Mapped[str] = mapped_column(Text, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProgrammaCache(Base):
    """Cache delle analisi /programma per il replay (query invece di rigenerare).

    GLOBALE (non per-utente): la scheda di un comune dipende dai parametri e
    dalle evidenze pubbliche, non da chi la chiede. Invalidata da
    `knowledge_version` (per comune) + TTL (`expires_at`). `scheda_json` è la
    `ProgrammaResponse` serializzata, restituita verbatim al hit.
    """

    __tablename__ = "programma_cache"
    __table_args__ = (
        Index("ix_programma_cache_comune", "cod_comune"),
        {"schema": "opendata"},
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    cache_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    cod_comune: Mapped[str] = mapped_column(Text, nullable=False)
    tema: Mapped[str | None] = mapped_column(Text, nullable=True)
    modalita: Mapped[str] = mapped_column(Text, nullable=False)
    knowledge_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    scheda_json: Mapped[str] = mapped_column(Text, nullable=False)
    generato_il: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
