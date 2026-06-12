# Spec 06 — Confini comunali su PostGIS + risoluzione spaziale

**Pezzo 6.** Lo strato geospaziale che sblocca il caso d'uso originale: **disegnare una
zona sulla mappa** e ottenere il/i comune/i corrispondenti, su cui poi gira l'analisi
del programma (Pezzo 4/5). Introduce PostGIS su Neon, i confini ISTAT, un MCP per le
query spaziali (agente) e un endpoint per la UI.

## Limite onesto da dichiarare

OpenCoesione georeferenzia i progetti **a livello comunale**, non con coordinate
puntuali sempre disponibili. Quindi un poligono disegnato si risolve in **comune/i
intersecati**; l'intersezione sotto-comunale reale (solo i progetti dentro il
poligono) sarà possibile solo per i progetti che espongono coordinate. La UI lo
comunica: "zona → comuni interessati", non "progetti dentro il poligono" salvo dato
puntuale disponibile.

## 6A — Store confini (backend, PostGIS su Neon)

- **Estensione**: la migrazione esegue `CREATE EXTENSION IF NOT EXISTS postgis`
  (supportata da Neon).
- **Tabella `opendata.comuni`**: `cod_comune` (ISTAT, unique), `nome`, `cod_provincia`,
  `cod_regione`, `geom geometry(MultiPolygon, 4326)`, `centroid geometry(Point, 4326)`,
  `popolazione?`, `ingested_at`. **Indice GIST** su `geom`.
- **Guard SQLite (test)**: come `_PK`/`_strip_schema`, le colonne `geometry` esistono
  solo su Postgres; nella suite SQLite vengono saltate e i test spaziali sono marcati
  `@pytest.mark.postgis` (non girano su SQLite). Il runtime è **sempre Postgres**
  (Neon in prod).
- **Ingest CLI `opendata-confini-sync`**: scarica i **confini amministrativi ISTAT**
  (unità amministrative a fini statistici, GeoJSON/Shapefile), riproietta a EPSG:4326
  se necessario (pyproj), calcola il centroide, upsert per `cod_comune`. Streaming/loop,
  non full-load. Attribuzione licenza ISTAT negli output.

## 6B — MCP `confini-mcp-server` (PostGIS-backed, agent-facing)

Nuovo server sul pattern di istat/opencoesione, **env-gated su `CONFINI_DB_URL`**
(senza, non parte / nessun tool). Connessione read-only, query PostGIS parametrizzate
(no SQL libero). Tool con prefisso `confini_`:

| tool | query | uso |
|---|---|---|
| `confini_resolve_point(lat, lon)` | `ST_Contains(geom, point)` | punto → comune |
| `confini_resolve_polygon(geojson)` | `ST_Intersects` + `ST_Area(ST_Intersection)` | poligono → comuni + % sovrapposizione |
| `confini_get_comune(cod_comune)` | select | confine (GeoJSON) + attributi |
| `confini_neighbors(cod_comune)` | `ST_Touches` | comuni confinanti |

Output con blocco `sources` (confini ISTAT + versione/data ingest). Annotations
read-only/idempotent. Validazione input GeoJSON con shapely.

## 6C — Endpoint backend `/geo/resolve` (per la UI)

L'agente usa l'MCP (R13); la **UI** non parla con gli MCP → endpoint dedicato.
- `POST /geo/resolve`, `Depends(enforce_rate_limit)`: body `{ geojson }` (Polygon o
  Point) → lista comuni intersecati `[{cod_comune, nome, overlap_pct}]`, ordinati per
  sovrapposizione. Interroga direttamente `opendata.comuni` (stessa tabella, sessione
  backend). Registrato in `main.py`.

## 6D — Frontend: "disegna la zona" sulla pagina programma

- Sulla pagina `app/programma` (Pezzo 5), aggiungere un controllo **Leaflet draw**
  (riusando l'infra mappa esistente, `output: 'export'`, `apiFetch`): l'utente disegna
  il poligono → `POST /geo/resolve` → comuni risolti → preselezione `cod_comune` →
  `POST /programma`.
- Se i comuni sono più d'uno, l'utente sceglie quale (o "tutti"). Messaggio sul limite
  di granularità.

## Layer & dipendenze

- `opendata_core/geo/` (DB-free): helper geometrici condivisi (validazione GeoJSON,
  bbox, riproiezione) con **shapely** (+ **pyproj** per la riproiezione dell'ingest).
  Aggiornare `opendata_core/pyproject.toml`.
- PostGIS SQL: via `sqlalchemy.text()` parametrizzato (no geoalchemy2 obbligatorio),
  così l'accoppiamento ORM resta leggero e il guard SQLite è semplice.
- `confini-mcp-server`: dipende da `opendata-core`, `shapely`; legge `CONFINI_DB_URL`.

## Integrazione

- `.env.*.example`: `CONFINI_DB_URL` (MCP), riuso `DATABASE_URL` per l'ingest,
  `CONFINI_BULK_URL`/versione ISTAT opzionale.
- `docker-compose.yml`: servizio `confini-mcp`; passare `CONFINI_DB_URL`.
- `Makefile`: `make confini-sync`, `make mcp-stdio-confini`.
- Neon: abilitare PostGIS una tantum (`CREATE EXTENSION postgis`) nel branch DB.

## Fuori scope

- Arricchimento territoriale (ISPRA consumo suolo/dissesto, OSM accessibilità) come
  fonti del fan-out = eventuale Pezzo 7.
- Intersezione sotto-comunale dei singoli progetti (richiede coordinate progetto).

## Definition of Done

- [ ] PostGIS abilitato su Neon; migrazione `comuni` (canonica submodule + stub mirror)
      con `CREATE EXTENSION`, geom + GIST; guard SQLite per i test.
- [ ] CLI `opendata-confini-sync`: download ISTAT, riproiezione 4326, centroide, upsert.
- [ ] `confini-mcp-server` con i 4 tool PostGIS, env-gated `CONFINI_DB_URL`, `sources`.
- [ ] `opendata_core/geo/` con shapely/pyproj; pyproject aggiornati.
- [ ] Endpoint `POST /geo/resolve` registrato; test su poligono noto → comuni attesi.
- [ ] Pagina programma: disegno poligono → resolve → `cod_comune` → programma; nota sul
      limite di granularità.
- [ ] `make lint && make test` verdi (test spaziali marcati postgis); `next build` verde.
- [ ] Smoke: disegno di un'area industriale su un comune pugliese → comune risolto →
      scheda programma generata.
