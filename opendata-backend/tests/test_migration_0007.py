"""Test upgrade/downgrade della migrazione 0007 (Fase 0) su Postgres+PostGIS.

La 0007 usa schema `opendata`, estensione PostGIS e tipo geometry: gira solo su
Postgres (come le 0001-0006). Su SQLite — il default di `make test`/CI, che non
ha Postgres — il test si salta. Per eseguirlo:

    DATABASE_URL=postgresql+asyncpg://opendata:opendata@localhost:15432/opendata \
        pytest tests/test_migration_0007.py

Il ciclo è idempotente e additivo (toggle 0006↔0007): non tocca i dati esistenti
e lascia il DB su head.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    "postgresql" not in DATABASE_URL,
    reason="0007 richiede Postgres+PostGIS; nessun DATABASE_URL postgres (CI gira su SQLite)",
)

_PREV = "0006_drop_documenti"
_TERRITORY = (
    "entities",
    "dataset_quality",
    "maturity_assessments",
    "place",
    "feature_store",
    "territory_reports",
    "population_profile",
    "business_cluster",
    "tourism_signal",
    "work_signal",
    "mobility_node",
    "weather_signal",
    "investment",
)


def _alembic_cfg():
    from alembic.config import Config

    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(ini.parent / "migrations"))
    return cfg


def _sync_engine():
    from opendata_backend.db.url import to_sync_dsn

    return create_engine(to_sync_dsn(DATABASE_URL))


def _table_count(conn, names: tuple[str, ...]) -> int:
    rows = conn.execute(
        text(
            "select count(*) from information_schema.tables "
            "where table_schema='opendata' and table_name = any(:names)"
        ),
        {"names": list(names)},
    )
    return int(rows.scalar_one())


def test_0007_upgrade_creates_territory_schema() -> None:
    from alembic import command

    cfg = _alembic_cfg()
    command.upgrade(cfg, "head")

    eng = _sync_engine()
    try:
        with eng.connect() as conn:
            assert _table_count(conn, _TERRITORY) == len(_TERRITORY)
            geom_udt = conn.execute(
                text(
                    "select udt_name from information_schema.columns where "
                    "table_schema='opendata' and table_name='place' and column_name='geom'"
                )
            ).scalar_one()
            assert geom_udt == "geometry"
            gist = conn.execute(
                text(
                    "select indexname from pg_indexes where schemaname='opendata' "
                    "and indexname='ix_place_geom'"
                )
            ).scalar_one_or_none()
            assert gist == "ix_place_geom"
    finally:
        eng.dispose()


def test_0007_downgrade_drops_only_territory() -> None:
    from alembic import command

    cfg = _alembic_cfg()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, _PREV)

    eng = _sync_engine()
    try:
        with eng.connect() as conn:
            assert _table_count(conn, _TERRITORY) == 0
            # le tabelle pre-esistenti restano (nessuna regressione)
            users = _table_count(conn, ("users",))
            assert users == 1
    finally:
        eng.dispose()
        command.upgrade(_alembic_cfg(), "head")  # ripristina head per gli altri usi
