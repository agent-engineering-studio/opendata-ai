# Fase 1 — Motore di maturità (ODM 2025 + AgID)

Data: 2026-06-17 · Branch: `feat/capability-layer` · Prereq: Fase 0 · Pilota: Comune di Gioia del Colle

## Decisioni
1. **Motore deterministico in `opendata_core.maturity`** (puro, NO LLM). maturity-mcp lo
   avvolge come tool + fa la propria chiamata Haiku; il router `/maturity` lo importa
   direttamente (niente accoppiamento backend→MCP a runtime) + persiste/cache.
2. **Semantico Haiku iniettato**: le funzioni di scoring ricevono `semantic_clarity`
   (0–1) come input opzionale; Haiku è chiamato solo dal layer MCP/backend (cache-ato).
   → unit test deterministici, niente rete in `make test`.
3. **POST /maturity/assess sincrono** con cap dataset (`MATURITY_MAX_DATASETS`, ~50) +
   cache Redis (TTL 24h) per ente; logga la troncatura.
4. **Pesi/livelli**: default in `opendata_core.maturity` (DEFAULT_WEIGHTS + soglie ODM);
   `config_data/maturity_weights.yaml` è l'override passato in dal backend (allineo i
   `levels` ai nomi ODM su 0–100).

## Motore (`opendata_core/maturity/`)
- `models.py`: `DatasetInput` (normalizzato da CKAN), `QualityScore`, `DimensionScores`, `MaturityResult`.
- `quality.py::assess_quality(ds, *, semantic_clarity=None)`:
  - **5-star** 0–5 (licenza aperta→1, strutturato proprietario→2, formato aperto→3, RDF/URI→4, linked→5).
  - **FAIR** F/A/I/R ∈[0,1] = frazione di check (vedi design).
  - **DCAT-AP_IT** ∈[0,1] = frazione campi obbligatori.
  - **ISO 25012** ∈[0,1] = media completezza/attualità/coerenza → `iso25012_jsonb`.
  - `freshness_days`, `license_open_bool`, `hvd_category`.
- `hvd.py`: 6 categorie HVD (Reg. UE 2023/138) per keyword/theme.
- `dimensions.py`: 4 dimensioni 0–100 (quality/portal/policy/impact) dai dataset dell'ente;
  `score_overall = Σ peso·dim`; livello ODM (Beginner/Follower/Fast-tracker/Trend-setter).
- `recommendations.py`: `{code, severity, dimension, message, affected_count}` dai gap.

## maturity-mcp (FastMCP, pattern *-mcp-server)
Tool: `harvest_entity`, `assess_quality` (+Haiku), `score_dimension`, `score_overall`, `compare_entities`.
Transport stdio+HTTP, porta 18087, Dockerfile (context repo root). Compose + Makefile
`mcp-stdio-maturity` + `CUSTOM_SERVICES` + matrici CI.

## Backend `/maturity` (auth + rate-limit + cache)
- POST `/maturity/assess` {entity, base_url?}: harvest(cap)→assess(+Haiku)→persisti snapshot→scorecard (cache 24h).
- GET `/maturity/entities/{id}`: scorecard (4 dim, livello, dettaglio, raccomandazioni) + trend.
- GET `/maturity/ranking?type=&region=`: benchmark + mediana cluster.
Persistenza storicizzata: `dataset_quality` (per dataset/snapshot) + `maturity_assessments`
(per ente/snapshot, `details_jsonb` = breakdown + raccomandazioni). Repos in `db/repositories/`.
Upsert `entities` via `extract_publisher`.

## Frontend
`app/scorecard/page.tsx` (`?entity=`, swr→apiFetch): radar 4 dim (recharts), badge livello,
raccomandazioni, trend storico, confronto mediana cluster. Stile design-react-kit. Link in nav.

## Test & docs
- opendata_core: unit 5-star/FAIR/DCAT/ISO/HVD/aggregazione con fixture.
- maturity-mcp: tool con CKAN mock + Haiku mock.
- backend: router con CKAN mock + SQLite + fakeredis.
- smoke `make mcp-stdio-maturity`. docs: `claude-desktop.md` + nota maturità in `data-model.md`.

## DoD
Scorecard riproducibile per Gioia del Colle · `make lint && make test` verdi.

## Commit
1. opendata_core.maturity + unit test + allineo maturity_weights.yaml
2. maturity-mcp server + test + compose/Makefile/CI
3. backend /maturity router + repos + cache + Haiku + test
4. frontend scorecard
5. docs + verifica DoD pilota
