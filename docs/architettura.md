# Architettura — capability layer (Fasi 0–5)

Il capability layer è costruito **sopra** il fan-out conversazionale esistente
(`/datasets/search`, `/programma`) senza riscritture: aggiunge un data warehouse
canonico (`opendata.*`), motori deterministici in `opendata_core`, endpoint REST
dedicati e un sito civico statico.

```mermaid
flowchart TD
  subgraph Fonti["Fonti (live)"]
    CKAN[CKAN dati.gov.it / regionali]
    SDMX[ISTAT / Eurostat / OECD]
    OSM[OSM Nominatim/Overpass]
    OC[OpenCoesione]
    METEO[Open-Meteo]
    GTFS[GTFS]
    WD[Wikidata]
  end

  subgraph Core["opendata_core (puro, deterministico)"]
    MAT[maturity: 5-star/FAIR/DCAT/ISO/HVD + dimensioni ODM]
    VAL[value: art.14 + combinabilità]
    TER[territory: resolve + profilo]
    CONN[connettori: ckan/sdmx/osm/opencoesione/meteo/gtfs/wikidata]
  end

  subgraph WH["Data warehouse opendata.* (Postgres+PostGIS)"]
    RAW[raw_ingest]
    ENT[entities · dataset_quality · maturity_assessments]
    PLACE[place · signal · investment · feature_store · territory_reports]
    CIVIC[civic_snapshots · community_*]
  end

  subgraph BE["opendata-backend (FastAPI)"]
    ETL[ETL Layer 1→2]
    FEAT[feature store Layer 3]
    MATSVC[/maturity/*]
    VALSVC[/value/*]
    TERSVC[/territory/*]
    UC[/usecases/* ApriQui · PugliaTrip]
    SHOW[/showcases/*]
    SITE[civic site export/preview]
    COMM[/community/*]
    BATCH[opendata-batch cron]
  end

  Fonti --> Core --> WH --> BE
  CONN --> ETL --> RAW
  ETL --> PLACE
  FEAT --> PLACE
  TER --> PLACE
  OC --> TERSVC --> PLACE
  MAT --> MATSVC --> ENT
  VAL --> VALSVC
  FEAT --> UC
  PLACE --> SHOW
  CIVIC --> SITE
  COMM --> CIVIC
  BATCH --> MATSVC
  BATCH --> CIVIC

  %% Anello valore<->maturità (Fase 5)
  TERSVC -. "gap di dato (domanda di riuso)" .-> MATSVC
  MATSVC -. "Impact penalizzato" .-> SITE
```

## Flussi chiave
- **Maturità** (Fase 1): harvest CKAN → `assess_entity` (deterministico) → `maturity_assessments`
  (snapshot storicizzati → trend) → scorecard / ranking / CSV.
- **Valore** (Fase 2): `estimate_value` (art.14) → `value_card` additivo in `/datasets/search`,
  `/value/portfolio`, narrazione Sonnet.
- **Territorio** (Fase 2): `/territory/report` dal modello canonico (profilo + investimenti OpenCoesione
  + segnali) + narrazione, persistito in `territory_reports`.
- **Use case** (Fase 3): ApriQui (attrattività esplicabile) e PugliaTrip (itinerari meteo-aware),
  region-agnostici; showcase-engine YAML.
- **Sito civico** (Fase 4): snapshot versionati + diff "fatto vs non fatto" → generatore Jinja2
  self-contained + community `/community/*`; check-in apre il thread di revisione.
- **Anello valore⇄maturità** (Fase 5): i gap di dato dei report Territorio (`/territory`) diventano
  "domanda di riuso non soddisfatta" che **penalizza l'Impact** dell'ente e compare nella scorecard e
  nel sito civico. Il **batch** (`opendata-batch`, cron) aggiorna maturità + snapshot in modo idempotente.

## Invarianti
- `opendata_core` resta **puro** (no FastMCP/FastAPI/LLM): semantico (Haiku) e pesi/penalità sono **iniettati**.
- Fonti live → tutto il codice che le usa è **fail-safe**; sotto soglia dataset l'assessment è
  **"dato insufficiente"** (no punteggi falsi).
- Schema `opendata.*` con `_PK` SQLite-safe + DDL geo/JSONB **dialect-aware** (Postgres reale, SQLite nei test).
- Sito civico self-contained (SVG inline; Leaflet via CDN) — riproducibilità (snapshot_id/fonti/KPI) e
  neutralità (ogni numero linkato a fonte+licenza).
