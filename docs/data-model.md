# Modello dati — ente + canonico territoriale (Fase 0)

Introdotto dalla migrazione `0007_phase0_foundations` come **capability layer**
additivo sopra lo schema esistente (`users/favorites/history/api_keys/
classifications/oc_progetti/comuni_anagrafica/programma_cache/...`). Nessuna
modifica alle tabelle pre-esistenti. Schema: **`opendata.*`**.

## Strategia geo / compatibilità test
- **Runtime**: Postgres 16 + **PostGIS 3.4** (immagine `postgis/postgis:16-3.4`).
  La migrazione esegue `CREATE EXTENSION IF NOT EXISTS postgis`.
- **Test** (`make test`/CI): SQLite, che non ha PostGIS né schema. Quindi:
  - `place.geom` è `geometry(GEOMETRY, 4326)` su Postgres e `TEXT` su SQLite
    (tipo ORM con base `Text` + variant `Geometry` su `postgresql`, così
    `geoalchemy2` non aggancia gli hook SpatiaLite su SQLite);
  - i campi `*_jsonb` sono `JSONB` su Postgres e `JSON` su SQLite;
  - DDL PostGIS (estensione, indice GiST) emesso solo se
    `dialect == postgresql` (come `migrations/env.py`).
- Il **test di migrazione** (`tests/test_migration_0007.py`) gira upgrade/downgrade
  su Postgres se `DATABASE_URL` è postgres, altrimenti si salta (CI su SQLite resta verde).

## Tabelle

### Ente / maturità
- **`entities`** `(id, name, type, ckan_org_id [unique], portal_url, region, ipa_code, created_at)`
  — l'ente titolare dei dati. `ckan_org_id` è la chiave di collegamento con i
  risultati CKAN (vedi *Publisher mapping*).
- **`dataset_quality`** `(id, entity_id→entities, source, dataset_id, assessed_at,
  stars_5, fair_f/a/i/r, dcat_ap_it_compliance, iso25012_jsonb, license_open_bool,
  hvd_category, freshness_days)` — valutazione qualità di un dataset (FAIR, 5-stars,
  DCAT-AP_IT, ISO 25012, HVD, freschezza).
- **`maturity_assessments`** `(id, entity_id→entities, assessed_at, score_policy,
  score_portal, score_quality, score_impact, score_overall, level, details_jsonb)`
  — maturità open-data dell'ente per dimensione. Pesi e soglie in
  `config_data/maturity_weights.yaml`.

### Canonico territoriale
- **`place`** `(id, istat_code [unique], name, geom, type)` — luogo (comune/…),
  `geom` = confine o centroide (SRID 4326). Indice GiST `ix_place_geom` (Postgres).
- **`feature_store`** `(id, place_id→place [unique], features_jsonb, computed_at)`
  — feature calcolate per luogo (cache).
- **`territory_reports`** `(id, place_id→place, created_at, payload_jsonb)`
  — report territoriali generati.
- **Signal** (skeleton Fase 0, stessa forma `id, place_id→place, source,
  observed_at, payload_jsonb`): `population_profile`, `business_cluster`,
  `tourism_signal`, `work_signal`, `mobility_node`, `weather_signal`,
  `investment`. Le colonne tipizzate specifiche arriveranno nelle fasi che le consumano.

### Relazioni (sintesi)
```
entities 1─* dataset_quality        (entity_id, ON DELETE SET NULL)
entities 1─* maturity_assessments   (entity_id, ON DELETE CASCADE)
place    1─1 feature_store           (place_id,  ON DELETE CASCADE, UNIQUE)
place    1─* territory_reports        (place_id,  ON DELETE CASCADE)
place    1─* <signal tables>          (place_id,  ON DELETE CASCADE)
```

## Publisher mapping (CKAN → entities)
`opendata_core.ckan.extract_publisher(pkg)` estrae l'ente da un pacchetto CKAN
(`organization` + extras DCAT-AP_IT `holder_identifier`/`publisher_*`) →
`PublisherRef(ckan_org_id, name, ipa_code, portal_url)`. `to_entity_fields(ref)`
produce il dict per l'upsert in `entities` con chiave `ckan_org_id`.

## Config
- `config_data/maturity_weights.yaml` — pesi per dimensione (policy/portal/quality/
  impact, somma 1.0) + soglie di livello.
- `config_data/value_taxonomy.yaml` — categorie di valore per la valorizzazione.
- Loader: `opendata_backend.config_files.maturity_weights()` / `value_taxonomy()`
  (cache-ati). Override dir via `OPENDATA_CONFIG_DIR`.

## Seed pilota
`opendata-territorio-seed` (`ingest/territory_seed.py`) — idempotente: upsert di
`place` "Gioia del Colle" (ISTAT **072021**, geom dal confine OSM/Nominatim con
fallback a centroide/NULL) ed `entities` "Comune di Gioia del Colle". Rieseguibile
senza duplicati. Richiede PostGIS. `--no-geometry` salta il fetch OSM.

## Maturità (Fase 1)
Le tabelle `entities`, `dataset_quality` e `maturity_assessments` sono popolate dal
**motore di maturità** (`opendata_core.maturity`, ODM 2025 + AgID):
- `dataset_quality`: uno snapshot per dataset/assessment (5-star, FAIR, DCAT-AP_IT,
  ISO 25012 in `iso25012_jsonb`, HVD, freshness);
- `maturity_assessments`: uno snapshot per ente/assessment con i 4 punteggi
  (policy/portal/quality/impact), `score_overall`, `level` (scala ODM:
  Beginner/Follower/Fast-tracker/Trend-setter) e `details_jsonb` (dimensioni +
  raccomandazioni). Gli snapshot storicizzati alimentano il **trend**.
- `entities` è upsertata per `ckan_org_id` (vedi `extract_publisher`).

Esposto da: server `maturity-mcp` (tool) e router backend `/maturity`
(`/assess`, `/entities/{id}`, `/ranking`) con cache Redis. Pesi/soglie in
`config_data/maturity_weights.yaml`. Scorecard pilota verificata riproducibile per
il Comune di Gioia del Colle (Beginner/0 su dati.gov.it: l'ente non vi espone dataset).

## Valore & Territorio (Fase 2)
Capability layer sopra il modello canonico, senza nuove migrazioni (riusa le tabelle di Fase 0).

**Valore** (`opendata_core.value`, art. 14 Dir. UE 2019/1024):
- `estimate_value(ds)` → 4 criteri (socio-economico, platea/PMI, proventi, combinabilità) + `combinability(ds)`.
- Backend: `value_card` opzionale e additivo su `Resource` in `POST /datasets/search` (retro-compatibile);
  `POST /value/narrative` (Sonnet, fallback offline); `GET /value/portfolio` (aggregati da `dataset_quality`
  + reuse da `favorites`/`classifications`). Frontend `/valore`.

**Territorio** (`opendata_core.territory` + `opendata_core.opencoesione`):
- `resolve_place` (OSM) + `build_profile` (popolazione ISTAT iniettata + POI OSM) → popola i signal.
- Investimenti: `OpenCoesioneClient` (REST live) → tabella `investment` (idempotente per place/sorgente).
- `POST /territory/report` `{istat_code, temi[], anno_da, anno_a}`: profilo + investimenti + servizi/
  accessibilità + segnali + idee (placeholder Fase 3) + gap di dato + narrazione Sonnet, persistito in
  `territory_reports`; profilo cache-ato in `feature_store`. `GET /territory/{istat}/profile`. Frontend
  `/territorio-report`. Distinto da `/programma` (fan-out conversazionale), che resta invariato.
- Pilota verificato end-to-end: Gioia del Colle (072021) — popolazione 27.889, ~127 POI commerciali OSM,
  50 progetti OpenCoesione (~€227M, top tema Trasporti/mobilità).

## ETL, feature store, showcase, use case (Fase 3)
- **Connettori** (`opendata_core`): `meteo` (Open-Meteo, CC BY), `gtfs` (parser→fermate),
  `wikidata` (SPARQL, CC0), `portals` (registro CKAN regionali, es. dati.puglia.it). Licenza tracciata.
- **ETL Layer 1→2**: `raw_ingest` (migrazione 0008, idempotente per sha, licenza) + `etl/` (record raw +
  GTFS→`mobility_node`). Signals/investimenti restano popolati dal report di Fase 2.
- **Feature store (Layer 3)**: `features/` materializza in `feature_store` densità competitor, accessibilità
  servizi, family-friendly, walkability proxy, distanza-da-fermata (GTFS), permanenza turistica (proxy);
  data-scarce (25–44/assunzioni/fragilità) → null + gap.
- **Showcase-engine**: `showcase/` interpreta `showcases_data/*.yaml` (sorgente canonica, indicatore, join
  spaziale per ISTAT, viz). GET `/showcases`, GET `/showcases/{id}/run`.
- **Use case** (endpoint dedicati): **ApriQui AI** (`POST /usecases/apriqui`) score attrattività 0–100 su
  10 categorie + spiegazione Sonnet + confronto; **PugliaTrip Brain** (`POST /usecases/pugliatrip`) itinerari
  meteo-aware (POI OSM + Open-Meteo + mobility) + spiegazione. **Region-agnostici** (qualunque comune). Le
  "idee di sviluppo" del report Territorio si popolano dalle top categorie ApriQui.
- **Frontend**: galleria `/usecases` (ApriQui bar chart, PugliaTrip itinerario + mappa OSM, showcase).
- Pilota verificato end-to-end (Gioia del Colle): ApriQui top categorie ~88/100; PugliaTrip 9 POI OSM su 3
  giorni meteo-aware. (OSM/Open-Meteo/Wikidata/OpenCoesione live → fail-safe.)

## Sito civico + accountability (Fase 4)
- **Snapshot versionati** (`civic_snapshots`, mig 0009): `(istat_code, snapshot_id)` UNIQUE → NON si
  sovrascrivono (2026-H1, 2026-H2…). `config_data/civic_kpi.yaml` definisce i KPI civici versionati.
  `civic/snapshot.py` crea lo snapshot (stato + KPI), `civic/diff.py` confronta due snapshot
  ("fatto vs non fatto" su opere programmato→concluso + KPI migliorati/peggiorati).
- **Generatore sito** (`civic/site.py`, Jinja2): bundle statico self-contained multi-pagina (Stato
  dell'arte/Investimenti/Opportunità/Rischi/Avanzamento/Community + Mappa + Scorecard maturità).
  Grafici SVG inline, mappa Leaflet CDN. Ogni pagina riporta snapshot_id/data/sources_version/kpi_version
  (riproducibilità) e linka fonte+licenza (neutralità). `POST /territory/{istat}/site/export` (zip),
  `GET /territory/{istat}/site/preview`. Anello valore⇄maturità: la scorecard dell'ente è linkata nel sito.
- **Community** (`/community/*`, tabelle `community_*`): thread per tema/opera/KPI/snapshot, post, ruoli
  cittadino/moderatore/amministratore (Clerk), moderazione, dati personali minimi (GDPR). Il **check-in**
  (`civic/checkin.py`) alla creazione di un nuovo snapshot apre un thread di revisione "cosa è cambiato".
- `POST /territory/{istat}/snapshot` crea lo snapshot e lancia il check-in.
- Pilota verificato end-to-end: Gioia del Colle con 2 snapshot (2026-H1/H2) → diff (3 opere concluse,
  2 KPI in miglioramento) + thread community + sito esportabile.

## Applicare le migrazioni
```bash
cd opendata-backend
DATABASE_URL=postgresql+asyncpg://opendata:opendata@localhost:15432/opendata \
  alembic upgrade head
# seed pilota
DATABASE_URL=... opendata-territorio-seed
```

> Allineamento submodule: come le 0001-0006, la 0007 è uno **stub** che rispecchia
> la migrazione canonica del submodule `vendor/agent-stack` (non materializzato in
> questo checkout). Quando il submodule sarà presente, aggiungere il gemello
> canonico e tenere lo stub in sync.
