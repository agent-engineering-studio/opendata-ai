# Fase 0 — Fondamenta: entità "ente" + modello canonico territoriale

Data: 2026-06-17 · Branch: `feat/capability-layer` · Pilota: Gioia del Colle (ISTAT 072021)

## Obiettivo
Introdurre l'entità **ente** e il **modello canonico territoriale** come capability
layer SOPRA il fan-out esistente, **senza regressioni** sugli endpoint attuali. Tutto
additivo (nuove tabelle/moduli), nessuna modifica a router/orchestrator esistenti.

## Decisioni di design
1. **Geo + test SQLite.** `make test` gira su SQLite (no PostGIS); `alembic upgrade head`
   su Postgres+PostGIS. Strategia (coerente con il dialect-guard già in `migrations/env.py`):
   - dep nuova `geoalchemy2`; colonna `geom` ORM = `Geometry("MULTIPOLYGON", srid=4326).with_variant(Text(), "sqlite")`
     (colonna presente su entrambi i dialetti);
   - in migrazione `CREATE EXTENSION IF NOT EXISTS postgis`, tipo `geometry(...)` e indice
     GiST emessi **solo** se `op.get_bind().dialect.name == "postgresql"`; su SQLite `geom` è TEXT.
   - JSONB: `sa.JSON().with_variant(JSONB, "postgresql")`.
2. **PostGIS image.** `postgres:16-alpine` → `postgis/postgis:16-3.4` (stesso major 16, riusa il volume).
3. **Seed geometria.** Fetch live OSM/Nominatim (`polygon_geojson`), fallback centroide.
4. **Signal tables**: skeleton minimo (`id, place_id, source, observed_at, payload_jsonb`).

## Modello dati (schema `opendata.*`)
- Ente/maturità: `entities`, `dataset_quality`, `maturity_assessments` (colonne da spec; jsonb come sopra).
- Canoniche: `place(id, istat_code UNIQUE, name, geom, type)`, `feature_store(place_id, features_jsonb, computed_at)`,
  `territory_reports(id, place_id, created_at, payload_jsonb)`.
- Signal (skeleton): `population_profile, business_cluster, tourism_signal, work_signal, mobility_node, weather_signal, investment`.
- `_PK` SQLite-safe; `__table_args__ = ({"schema":"opendata"},)`; FK su `place_id`/`entity_id`.
- Nuovo modulo ORM `db/territory_models.py` (riusa `Base, _PK` → stessa `Base.metadata`, visibile ad Alembic).

## Componenti
- Migrazione `migrations/versions/0007_phase0_foundations.py` (down_revision `0006_drop_documenti`);
  `downgrade()` droppa solo le tabelle (NON l'estensione). Nota di allineamento al submodule `vendor/agent-stack`.
- Pydantic: `schemas/territory.py` (Entity, DatasetQuality, MaturityAssessment, Place, …).
- `opendata_core/ckan/publisher.py`: `extract_publisher(ckan_pkg) -> PublisherRef` + `to_entity_fields()` (mapping ckan_org_id → entities). No FastAPI/LLM.
- `opendata_core/osm`: `geocode_boundary(query)` → geometria GeoJSON + centroide (per il seed).
- Config: `opendata-backend/config/{maturity_weights,value_taxonomy}.yaml` + loader `config_files.py` (dep `pyyaml`).
- Seed: console script `opendata-territorio-seed` → `ingest/territory_seed.py:main`, idempotente
  (upsert per `istat_code` / nome ente), geometria via OSM con fallback centroide.
- Infra: `docker-compose.yml` → `postgis/postgis:16-3.4`.

## Test & docs
- `tests/test_migration_0007.py`: upgrade→downgrade su SQLite (geo guardato).
- `opendata_core` `tests/test_publisher.py`: estrazione + mapping da fixture CKAN.
- `docs/data-model.md`: nuovo modello (note PostGIS/SQLite).

## DoD
`alembic upgrade head` OK · `make lint && make test` verdi · seed eseguibile · docs aggiornate.

## Piano commit (piccoli)
1. infra: PostGIS image + deps (`geoalchemy2`, `pyyaml`)
2. ORM `territory_models.py` + Pydantic `schemas/territory.py`
3. migrazione 0007 + test up/down + nota vendor
4. `opendata_core` publisher helper + `geocode_boundary` + test
5. config yaml + loader
6. seed script idempotente
7. docs data-model
