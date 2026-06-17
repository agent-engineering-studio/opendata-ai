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
