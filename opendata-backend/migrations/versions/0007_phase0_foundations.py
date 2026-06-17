"""Fase 0 — ente + modello canonico territoriale (PostGIS).

Stub mirror della migrazione canonica che appartiene al submodule agent-stack
(`vendor/agent-stack/db/migrations/opendata/`). Il submodule non è materializzato
in questo checkout: quando lo sarà, aggiungere il gemello canonico lì e tenere
questo stub in sync (stesse tabelle, colonne, vincoli). Vedi
db/territory_models.py per i modelli ORM corrispondenti.

Tutto additivo: nessuna modifica alle tabelle esistenti (0001-0006).

Geo/JSONB sono dialect-aware (come migrations/env.py):
  - su PostgreSQL: CREATE EXTENSION postgis, geom = geometry(MultiPolygon,4326),
    indice GiST, *_jsonb = JSONB;
  - su SQLite (test): geom = TEXT, *_jsonb = JSON, niente estensione/GiST.

Revision ID: 0007_phase0_foundations
Revises: 0006_drop_documenti
Create Date: 2026-06-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision: str = "0007_phase0_foundations"
down_revision: Union[str, None] = "0006_drop_documenti"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# JSONB su Postgres, JSON su SQLite.
_JSONB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

_SIGNAL_TABLES = (
    "population_profile",
    "business_cluster",
    "tourism_signal",
    "work_signal",
    "mobility_node",
    "weather_signal",
    "investment",
)


def _ts(nullable: bool = False) -> sa.Column:
    return sa.Column(
        "observed_at",
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=sa.text("now()"),
    )


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    op.execute("CREATE SCHEMA IF NOT EXISTS opendata")
    if is_pg:
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # geometry generico (non MULTIPOLYGON): accoglie confini poligonali e il
    # fallback a centroide (Point) del seed. SRID 4326.
    geom_type = (
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False)
        if is_pg
        else sa.Text()
    )

    # ── entities ──
    op.create_table(
        "entities",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=True),
        sa.Column("ckan_org_id", sa.Text(), nullable=True),
        sa.Column("portal_url", sa.Text(), nullable=True),
        sa.Column("region", sa.Text(), nullable=True),
        sa.Column("ipa_code", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("ckan_org_id", name="uq_entities_ckan_org_id"),
        schema="opendata",
    )
    op.create_index("ix_entities_ckan_org_id", "entities", ["ckan_org_id"], schema="opendata")

    # ── place ──
    op.create_table(
        "place",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("istat_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("geom", geom_type, nullable=True),
        sa.Column("type", sa.Text(), nullable=True),
        sa.UniqueConstraint("istat_code", name="uq_place_istat_code"),
        schema="opendata",
    )
    op.create_index("ix_place_type", "place", ["type"], schema="opendata")
    if is_pg:
        op.create_index(
            "ix_place_geom", "place", ["geom"], schema="opendata", postgresql_using="gist"
        )

    # ── dataset_quality ──
    op.create_table(
        "dataset_quality",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("dataset_id", sa.Text(), nullable=False),
        sa.Column(
            "assessed_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("stars_5", sa.Integer(), nullable=True),
        sa.Column("fair_f", sa.Numeric(5, 2), nullable=True),
        sa.Column("fair_a", sa.Numeric(5, 2), nullable=True),
        sa.Column("fair_i", sa.Numeric(5, 2), nullable=True),
        sa.Column("fair_r", sa.Numeric(5, 2), nullable=True),
        sa.Column("dcat_ap_it_compliance", sa.Numeric(5, 2), nullable=True),
        sa.Column("iso25012_jsonb", _JSONB, nullable=True),
        sa.Column("license_open_bool", sa.Boolean(), nullable=True),
        sa.Column("hvd_category", sa.Text(), nullable=True),
        sa.Column("freshness_days", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["entity_id"], ["opendata.entities.id"],
            name="fk_dataset_quality_entity", ondelete="SET NULL",
        ),
        schema="opendata",
    )
    op.create_index(
        "ix_dataset_quality_source_dataset", "dataset_quality",
        ["source", "dataset_id"], schema="opendata",
    )
    op.create_index(
        "ix_dataset_quality_entity", "dataset_quality", ["entity_id"], schema="opendata"
    )

    # ── maturity_assessments ──
    op.create_table(
        "maturity_assessments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "assessed_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("score_policy", sa.Numeric(5, 2), nullable=True),
        sa.Column("score_portal", sa.Numeric(5, 2), nullable=True),
        sa.Column("score_quality", sa.Numeric(5, 2), nullable=True),
        sa.Column("score_impact", sa.Numeric(5, 2), nullable=True),
        sa.Column("score_overall", sa.Numeric(5, 2), nullable=True),
        sa.Column("level", sa.Text(), nullable=True),
        sa.Column("details_jsonb", _JSONB, nullable=True),
        sa.ForeignKeyConstraint(
            ["entity_id"], ["opendata.entities.id"],
            name="fk_maturity_entity", ondelete="CASCADE",
        ),
        schema="opendata",
    )
    op.create_index(
        "ix_maturity_entity", "maturity_assessments", ["entity_id"], schema="opendata"
    )

    # ── feature_store ──
    op.create_table(
        "feature_store",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("place_id", sa.BigInteger(), nullable=False),
        sa.Column("features_jsonb", _JSONB, nullable=True),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["place_id"], ["opendata.place.id"],
            name="fk_feature_store_place", ondelete="CASCADE",
        ),
        sa.UniqueConstraint("place_id", name="uq_feature_store_place"),
        schema="opendata",
    )

    # ── territory_reports ──
    op.create_table(
        "territory_reports",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("place_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("payload_jsonb", _JSONB, nullable=True),
        sa.ForeignKeyConstraint(
            ["place_id"], ["opendata.place.id"],
            name="fk_territory_reports_place", ondelete="CASCADE",
        ),
        schema="opendata",
    )
    op.create_index(
        "ix_territory_reports_place", "territory_reports", ["place_id"], schema="opendata"
    )

    # ── signal tables (skeleton) ──
    for name in _SIGNAL_TABLES:
        op.create_table(
            name,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("place_id", sa.BigInteger(), nullable=False),
            sa.Column("source", sa.Text(), nullable=True),
            _ts(),
            sa.Column("payload_jsonb", _JSONB, nullable=True),
            sa.ForeignKeyConstraint(
                ["place_id"], ["opendata.place.id"],
                name=f"fk_{name}_place", ondelete="CASCADE",
            ),
            schema="opendata",
        )
        op.create_index(f"ix_{name}_place", name, ["place_id"], schema="opendata")


def downgrade() -> None:
    # Drop in ordine inverso alle FK: prima i figli, poi place/entities.
    for name in reversed(_SIGNAL_TABLES):
        op.drop_index(f"ix_{name}_place", table_name=name, schema="opendata")
        op.drop_table(name, schema="opendata")

    op.drop_index(
        "ix_territory_reports_place", table_name="territory_reports", schema="opendata"
    )
    op.drop_table("territory_reports", schema="opendata")

    op.drop_table("feature_store", schema="opendata")

    op.drop_index("ix_maturity_entity", table_name="maturity_assessments", schema="opendata")
    op.drop_table("maturity_assessments", schema="opendata")

    op.drop_index(
        "ix_dataset_quality_entity", table_name="dataset_quality", schema="opendata"
    )
    op.drop_index(
        "ix_dataset_quality_source_dataset", table_name="dataset_quality", schema="opendata"
    )
    op.drop_table("dataset_quality", schema="opendata")

    if op.get_bind().dialect.name == "postgresql":
        op.drop_index("ix_place_geom", table_name="place", schema="opendata")
    op.drop_index("ix_place_type", table_name="place", schema="opendata")
    op.drop_table("place", schema="opendata")

    op.drop_index("ix_entities_ckan_org_id", table_name="entities", schema="opendata")
    op.drop_table("entities", schema="opendata")
    # NB: non si droppa l'estensione postgis né lo schema opendata (condivisi).
