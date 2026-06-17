# Fase 3 — ETL, feature store, showcase-engine, use case (ApriQui, PugliaTrip)

Data: 2026-06-17 · Branch: `feat/capability-layer` · Prereq: Fasi 0–2 · Pilota: Gioia del Colle (072021)

## Decisioni
1. Raw versioning = tabella **`opendata.raw_ingest`** (migrazione 0008), idempotente per sha, licenza tracciata.
2. Feature store = feature **calcolabili ora** + gap documentati per le data-scarce (25–44/assunzioni/fragilità).
3. Use case = **endpoint dedicati** (logica ricca + Sonnet); showcase-engine YAML separato per gli showcase dichiarativi.
4. Connettori: **Open-Meteo**, **GTFS→mobility_node**, **dati.puglia.it** (config CKAN, no nuovo client), **Wikidata SPARQL**.
5. Tutto ciò che usa fonti live (OSM/Open-Meteo/Wikidata/OpenCoesione) è fail-safe (come Fase 2).

## Stream C — Connettori + ETL
- `opendata_core/meteo` (Open-Meteo forecast lat/lon), `opendata_core/gtfs` (parse zip → fermate),
  `opendata_core/wikidata` (SPARQL enrichment comune), `dati.puglia.it` = costante config CKAN.
- `raw_ingest` (migrazione 0008): source, dataset_id, fetched_at, license, sha, payload_jsonb.
- Backend `etl/`: registra raw + popola signals/mobility_node (CKAN regionale + ISTAT + OSM + GTFS), idempotente.

## Stream D — Feature store
- Backend `features/`: materializza in `feature_store` densità competitor, POI family-friendly, accessibilità
  servizi, walkability proxy, distanza-da-fermata (GTFS), permanenza turistica (best-effort); data-scarce → null+gap.

## Stream E — Showcase-engine
- Interprete `showcases/*.yaml` (sources, join spaziale/temporale, indicatore, visualizzazione). GET /showcases,
  GET /showcases/{id}/run. 1–2 fixture.

## Stream F — Use case
- ApriQui AI: score attrattività 0–100 / 10 categorie attività + spiegazione Sonnet + confronto. POST /usecases/apriqui.
- PugliaTrip Brain: itinerari meteo-aware (POI + mobility + Open-Meteo) + spiegazione. POST /usecases/pugliatrip.
- Le "idee di sviluppo" del report Territorio si popolano dall'output ApriQui.

## Stream G — Frontend
- Galleria use case + scheda con mappa (Leaflet) e spiegazione.

## Test & DoD
Unit feature/join; showcase-engine con YAML fixture; smoke 2 use case sul pilota.
DoD: ≥2 use case navigabili end-to-end su Gioia del Colle; make lint && make test verdi.

## Commit
C1 connettori+test · C2 migrazione 0008 raw_ingest+test · C3 ETL+test · D1 feature store+test ·
E1 showcase-engine+endpoint+fixture+test · F1 ApriQui+test · F2 PugliaTrip+test · F3 link idee ·
G1 frontend · docs+pilota.
