# Prompt Claude Code — P06: confini comunali su PostGIS + risoluzione spaziale

> Eseguire dalla root di `opendata-ai`, **dopo** i Pezzi 1–5. Leggi `CLAUDE.md`
> (R1, R3, R4, R6, R12, R13) e `docs/specs/06-confini-postgis.md`. Tocchi più package:
> `opendata_core/` (geo helper), `opendata-backend/` (tabella + ingest + endpoint),
> `confini-mcp-server/` (nuovo), `opendata-ai-ui/` (disegno).

---

Introduci lo strato geospaziale: confini comunali ISTAT su **PostGIS (Neon)** e la
risoluzione **poligono → comune/i**, così la UI del programma può partire da una zona
disegnata. **Limite onesto**: OpenCoesione è a granularità comunale → un poligono si
risolve in comuni intersecati, non in "progetti dentro il poligono". Dichiaralo nella UI.

Sequenzia: **6A (store+ingest) → 6B (MCP) → 6C (endpoint) → 6D (frontend)**.

Studia prima: `opendata-backend/db/models.py` (`Base`, `_PK`, schema), `db/session.py`,
`migrations/versions/0001_initial.py`, `cli.py`; `istat-mcp-server/` e
`opencoesione-mcp-server/` (pattern MCP, transport, env-gating del Pezzo 3);
`opendata_core/osm/` (stile core, già fa GeoJSON); `routers/datasets.py` (pattern
endpoint, `/datasets/proxy`); `app/mappa/` (Leaflet/draw, `apiFetch`).

## 6A — Store confini (backend, PostGIS)

1. **opendata_core/geo/** (DB-free): helper con **shapely** (validazione/parse GeoJSON,
   bbox) e **pyproj** (riproiezione a EPSG:4326). Aggiorna `opendata_core/pyproject.toml`
   (shapely, pyproj).
2. **Tabella `opendata.comuni`** in `db/models.py` (o `db/models_geo.py`): `cod_comune`
   unique, `nome`, `cod_provincia`, `cod_regione`, `geom geometry(MultiPolygon,4326)`,
   `centroid geometry(Point,4326)`, `popolazione?`, `ingested_at`; indice GIST su geom.
   **Guard SQLite**: le colonne geometry esistono solo su Postgres; nella suite SQLite
   vanno saltate (pattern analogo a `_PK`/`_strip_schema`) e i test spaziali marcati
   `@pytest.mark.postgis`.
3. **Migrazione**: canonica nel submodule `vendor/agent-stack` + **stub mirror**
   `migrations/versions/000X_comuni.py`, che inizia con
   `op.execute("CREATE EXTENSION IF NOT EXISTS postgis")` e
   `CREATE SCHEMA IF NOT EXISTS opendata`. Verifica `alembic upgrade head` su Postgres.
4. **CLI `opendata-confini-sync`** (pattern `cli.py`/`[project.scripts]`): scarica i
   confini amministrativi ISTAT (unità amministrative a fini statistici), riproietta a
   4326 con pyproj se serve, calcola centroide, **upsert per cod_comune** (usa
   `ST_GeomFromGeoJSON`/WKT via `text()` parametrizzato). Riusa `DATABASE_URL`.

## 6B — MCP `confini-mcp-server` (nuovo)

Clona la struttura di `opencoesione-mcp-server`. **Env-gated su `CONFINI_DB_URL`**:
senza, niente tool DB. Connessione read-only, **PostGIS via `sqlalchemy.text()`
parametrizzato** (no SQL libero). Tool prefisso `confini_`:
- `confini_resolve_point(lat, lon)` → `ST_Contains(geom, ST_SetSRID(ST_Point(lon,lat),4326))`;
- `confini_resolve_polygon(geojson)` → `ST_Intersects` + percentuale via
  `ST_Area(ST_Intersection(...))/ST_Area(input)`; valida il GeoJSON con shapely (core);
- `confini_get_comune(cod_comune)` → attributi + `ST_AsGeoJSON(geom)`;
- `confini_neighbors(cod_comune)` → `ST_Touches`.
Output con blocco `sources` (confini ISTAT + data ingest). Annotations read-only/idempotent.
`server.py` con lo stesso switch `TRANSPORT` (stdio/streamable-http/sse) + `/healthz`.

## 6C — Endpoint backend `/geo/resolve`

In un nuovo `routers/geo.py`: `POST /geo/resolve`, `Depends(enforce_rate_limit)`, body
`{geojson}` (Polygon o Point) → `[{cod_comune, nome, overlap_pct}]` ordinati per
sovrapposizione, interrogando `opendata.comuni` con la sessione backend. Registra il
router in `main.py`. (L'agente usa l'MCP; la UI usa questo endpoint — R13.)

## 6D — Frontend: disegno zona sulla pagina programma

In `app/programma/page.tsx` (Pezzo 5): aggiungi un controllo **Leaflet draw** (riusa
l'infra di `app/mappa/`, static export, `apiFetch`). Flusso: disegna poligono →
`POST /geo/resolve` → se più comuni, l'utente sceglie (o "tutti") → preselezione
`cod_comune` → `POST /programma`. Mostra la **nota sul limite di granularità**.

## Integrazione

- `.env.*.example`: `CONFINI_DB_URL` (MCP), `CONFINI_BULK_URL`/versione ISTAT opzionale;
  l'ingest usa `DATABASE_URL`.
- `docker-compose.yml`: servizio `confini-mcp` con `CONFINI_DB_URL`.
- `Makefile`: `make confini-sync`, `make mcp-stdio-confini`.
- **Neon**: abilita PostGIS una tantum sul branch DB (`CREATE EXTENSION postgis`).

## Vincoli

- R1 build context repo root per i Dockerfile. R4 schema `opendata`; runtime Postgres,
  guard SQLite per i test (geometry marcata postgis). R13 dati all'agente via MCP, UI
  via endpoint backend. R6 nessun `app/api/*` nel frontend. R12 `make lint && make
  test` prima del commit.
- Niente ISPRA/OSM-enrichment qui (Pezzo 7).

## Output atteso

opendata_core/geo (shapely/pyproj); tabella `comuni` + migrazione PostGIS + CLI di sync;
`confini-mcp-server` con 4 tool; endpoint `/geo/resolve`; disegno zona nella pagina
programma. `make lint && make test` verdi (spaziali marcati postgis), `next build`
verde. Smoke: disegno di un'area industriale su un comune pugliese → comune risolto →
scheda programma. Riepiloga per aggiornare la spec.
