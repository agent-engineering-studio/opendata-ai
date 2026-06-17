"""SQLAlchemy ORM per il modello canonico territoriale + ente/maturità (Fase 0).

Mirror dello schema `opendata.*` introdotto dalla migrazione
`0007_phase0_foundations`. Riusa `Base` e `_PK` di `db.models` (stessa
`Base.metadata`, così Alembic e `create_all` li vedono).

Geo: la colonna `geom` è `geometry(MULTIPOLYGON, 4326)` su Postgres+PostGIS e
`TEXT` su SQLite (test) via `with_variant`. I campi *_jsonb sono `JSONB` su
Postgres e `JSON` su SQLite. Coerente col dialect-guard di `migrations/env.py`.

Tabelle additive: NESSUNA modifica alle entità esistenti, nessuna regressione.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, _PK

# JSONB su Postgres, JSON su SQLite (test). Centralizzato per coerenza.
_JSONB = JSON().with_variant(JSONB(), "postgresql")

# geometry(Geometry,4326) su Postgres, TEXT su SQLite. Tipo generico (non
# MULTIPOLYGON) per accogliere sia i confini poligonali sia il fallback a
# centroide (Point) del seed. Tipo BASE = Text: così su SQLite geoalchemy2 NON
# aggancia gli hook SpatiaLite (RecoverGeometryColumn). La migrazione crea la
# colonna geometry reale + l'indice GiST (solo su postgresql); spatial_index=False
# evita auto-indici in eventuali create_all.
_GEOM = Text().with_variant(
    Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False), "postgresql"
)


# ── Ente / maturità ──────────────────────────────────────────────────


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (
        Index("ix_entities_ckan_org_id", "ckan_org_id"),
        {"schema": "opendata"},
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str | None] = mapped_column(Text, nullable=True)
    ckan_org_id: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    portal_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    region: Mapped[str | None] = mapped_column(Text, nullable=True)
    ipa_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DatasetQuality(Base):
    __tablename__ = "dataset_quality"
    __table_args__ = (
        Index("ix_dataset_quality_source_dataset", "source", "dataset_id"),
        Index("ix_dataset_quality_entity", "entity_id"),
        {"schema": "opendata"},
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("opendata.entities.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_id: Mapped[str] = mapped_column(Text, nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    stars_5: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fair_f: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    fair_a: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    fair_i: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    fair_r: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    dcat_ap_it_compliance: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    iso25012_jsonb: Mapped[dict[str, Any] | None] = mapped_column(_JSONB, nullable=True)
    license_open_bool: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    hvd_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    freshness_days: Mapped[int | None] = mapped_column(Integer, nullable=True)


class MaturityAssessment(Base):
    __tablename__ = "maturity_assessments"
    __table_args__ = (
        Index("ix_maturity_entity", "entity_id"),
        {"schema": "opendata"},
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("opendata.entities.id", ondelete="CASCADE"), nullable=False
    )
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    score_policy: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    score_portal: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    score_quality: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    score_impact: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    score_overall: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    level: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_jsonb: Mapped[dict[str, Any] | None] = mapped_column(_JSONB, nullable=True)


# ── Canoniche territoriali ───────────────────────────────────────────


class Place(Base):
    __tablename__ = "place"
    __table_args__ = (
        Index("ix_place_type", "type"),
        {"schema": "opendata"},
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    istat_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    geom = mapped_column(_GEOM, nullable=True)
    type: Mapped[str | None] = mapped_column(Text, nullable=True)


class FeatureStore(Base):
    __tablename__ = "feature_store"
    __table_args__ = ({"schema": "opendata"},)

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    place_id: Mapped[int] = mapped_column(
        ForeignKey("opendata.place.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    features_jsonb: Mapped[dict[str, Any] | None] = mapped_column(_JSONB, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TerritoryReport(Base):
    __tablename__ = "territory_reports"
    __table_args__ = (
        Index("ix_territory_reports_place", "place_id"),
        {"schema": "opendata"},
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    place_id: Mapped[int] = mapped_column(
        ForeignKey("opendata.place.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload_jsonb: Mapped[dict[str, Any] | None] = mapped_column(_JSONB, nullable=True)


# ── Signal (skeleton minimo, Fase 0) ─────────────────────────────────
# Ogni segnale territoriale: id, place_id, source, observed_at, payload_jsonb.
# Le colonne tipizzate specifiche arriveranno nelle fasi che le consumano (YAGNI).


def _signal_table_args(name: str) -> tuple[Any, ...]:
    return (Index(f"ix_{name}_place", "place_id"), {"schema": "opendata"})


class PopulationProfile(Base):
    __tablename__ = "population_profile"
    __table_args__ = _signal_table_args("population_profile")

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    place_id: Mapped[int] = mapped_column(
        ForeignKey("opendata.place.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload_jsonb: Mapped[dict[str, Any] | None] = mapped_column(_JSONB, nullable=True)


class BusinessCluster(Base):
    __tablename__ = "business_cluster"
    __table_args__ = _signal_table_args("business_cluster")

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    place_id: Mapped[int] = mapped_column(
        ForeignKey("opendata.place.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload_jsonb: Mapped[dict[str, Any] | None] = mapped_column(_JSONB, nullable=True)


class TourismSignal(Base):
    __tablename__ = "tourism_signal"
    __table_args__ = _signal_table_args("tourism_signal")

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    place_id: Mapped[int] = mapped_column(
        ForeignKey("opendata.place.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload_jsonb: Mapped[dict[str, Any] | None] = mapped_column(_JSONB, nullable=True)


class WorkSignal(Base):
    __tablename__ = "work_signal"
    __table_args__ = _signal_table_args("work_signal")

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    place_id: Mapped[int] = mapped_column(
        ForeignKey("opendata.place.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload_jsonb: Mapped[dict[str, Any] | None] = mapped_column(_JSONB, nullable=True)


class MobilityNode(Base):
    __tablename__ = "mobility_node"
    __table_args__ = _signal_table_args("mobility_node")

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    place_id: Mapped[int] = mapped_column(
        ForeignKey("opendata.place.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload_jsonb: Mapped[dict[str, Any] | None] = mapped_column(_JSONB, nullable=True)


class WeatherSignal(Base):
    __tablename__ = "weather_signal"
    __table_args__ = _signal_table_args("weather_signal")

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    place_id: Mapped[int] = mapped_column(
        ForeignKey("opendata.place.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload_jsonb: Mapped[dict[str, Any] | None] = mapped_column(_JSONB, nullable=True)


class Investment(Base):
    __tablename__ = "investment"
    __table_args__ = _signal_table_args("investment")

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    place_id: Mapped[int] = mapped_column(
        ForeignKey("opendata.place.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload_jsonb: Mapped[dict[str, Any] | None] = mapped_column(_JSONB, nullable=True)


# ── ETL Layer 1 (raw versionato) ─────────────────────────────────────


class RawIngest(Base):
    """Snapshot grezzo versionato di una risorsa esterna (ETL Layer 1→2).

    Idempotente per `sha` (hash del payload): la stessa risorsa non si duplica.
    La licenza è tracciata per ogni record.
    """

    __tablename__ = "raw_ingest"
    __table_args__ = (
        Index("ix_raw_ingest_source_dataset", "source", "dataset_id"),
        UniqueConstraint("sha", name="uq_raw_ingest_sha"),
        {"schema": "opendata"},
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    license: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha: Mapped[str] = mapped_column(Text, nullable=False)
    payload_jsonb: Mapped[dict[str, Any] | None] = mapped_column(_JSONB, nullable=True)


__all__ = [
    "Entity",
    "RawIngest",
    "DatasetQuality",
    "MaturityAssessment",
    "Place",
    "FeatureStore",
    "TerritoryReport",
    "PopulationProfile",
    "BusinessCluster",
    "TourismSignal",
    "WorkSignal",
    "MobilityNode",
    "WeatherSignal",
    "Investment",
]
