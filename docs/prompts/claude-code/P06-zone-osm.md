# Prompt Claude Code — P06: selezione zona via tag OSM

> Eseguire dalla root di `opendata-ai`, **dopo** i Pezzi 1–5. Leggi `CLAUDE.md`
> (R1, R3, R6, R7, R12, R13) e `docs/specs/06-zone-osm.md`. Tocchi tre package:
> `opendata_core/` (zone via Overpass), `osm-mcp/` (3 tool nuovi),
> `opendata-backend/` (endpoint UI) e `opendata-ai-ui/` (selettore zona).
> **Niente PostGIS, niente tabelle nuove, niente MCP server nuovo.**

---

La zona di analisi si **seleziona tra entità OSM riconosciute** (zone industriali,
commerciali, porto, centro storico…) trovate via tag dentro il comune. Chiave: i
confini comunali italiani su OSM portano `ref:ISTAT` sugli `admin_level=8`, quindi
l'ancoraggio comune → zone è una query Overpass con filtro ad area. Ogni zona ha
nome, `osm_id` e URL citabile (licenza ODbL) — coerente col modello evidence-based.

Studia prima: `opendata_core/src/opendata_core/osm/client.py` (`overpass_around`/
`overpass_bbox`: riusa `_http()`, settings, stile), `osm/geojson.py`,
`osm/settings.py`; `osm-mcp/src/.../tools.py` (pattern di registrazione, annotations,
`sources`); `opendata-backend/routers/datasets.py` (pattern endpoint, rate limit,
cache Redis); `app/mappa/` e la pagina `/territorio` del Pezzo 5.

## Fase 0 — Discovery (NON saltare)

Su 3–4 comuni pugliesi campione di taglia diversa, con query Overpass live:
1. verifica `ref:ISTAT` sugli `admin_level=8`;
2. per ogni `zona_tipo` della tassonomia (vedi spec, tabella tipo→tag): quanti
   poligoni, quanti con `name`;
3. trova un caso di **centro storico non mappato** e valida la catena di fallback;
4. salva 2–3 risposte Overpass reali (way chiuso, relation multipolygon con inner,
   elemento senza nome) come **fixture di test**.
Annota gli esiti in `opendata_core/osm/zones.py` e nel README di `osm-mcp`
(sezione "API Notes — zone").

## 1 — Core client (`opendata_core/osm/`)

Nuovo `zones.py` (+ estensioni a `geojson.py`), nessuna dipendenza nuova:
- enum `ZonaTipo` (`industriale | commerciale | portuale | centro_storico | verde |
  agricola`) + mappa tipo→filtri Overpass in **un solo posto**;
- `lookup_comune(nome)` → `[{nome, ref_istat, osm_id}]` (Overpass su
  `boundary=administrative` + `admin_level=8` + name case-insensitive);
- `list_zones(ref_istat, zona_tipo)` → query con `area[...]->.a; (way[...](area.a);
  relation[...](area.a);); out geom tags;` → `[{osm_type, osm_id, name?, zona_tipo,
  area_m2, centroid, bbox, osm_url}]`, nominati prima, poi per area decrescente;
- `get_zone(osm_type, osm_id)` → Feature GeoJSON completa;
- `geojson.py`: `overpass_to_features(elements)` — way chiusi → Polygon, relation
  multipolygon → assemblaggio outer/inner in puro Python. **Testalo con le fixture
  della discovery** (è l'unico pezzo non banale);
- catena di fallback in `list_zones`: tag → `geocode()` Nominatim su
  `"<label tipo> <comune>"` → lista vuota con `fallback_level` esplicito;
- cache TTL (`cachetools`) + un retry con backoff su 429/504 Overpass.

## 2 — Tool MCP (`osm-mcp`, accanto a quelli esistenti)

- `osm_lookup_comune(nome)`, `osm_list_zones(cod_comune, zona_tipo)`,
  `osm_get_zone(osm_type, osm_id)`;
- `response_format` markdown/json; annotations read-only/idempotent;
- blocco `sources` con "© OpenStreetMap contributors, ODbL" + URL entità; ogni
  risultato include `source_url` (contratto cattura citazioni, come Pezzo 2);
- `osm_list_zones` dichiara nel risultato il `fallback_level` usato.

## 3 — Endpoint backend (`routers/territorio.py`, nuovo)

La UI non parla con gli MCP (R13): il backend importa **direttamente**
`opendata_core.osm` (shared lib, nessun hop MCP):
- `GET /territorio/comuni?q=<nome>` → lookup;
- `GET /territorio/zone?cod_comune=&tipo=` → candidati GeoJSON + `fallback_level`;
- entrambi `Depends(enforce_rate_limit)` (R7), **cache Redis TTL 24h** chiave
  `(cod_comune, tipo)`; registra in `main.py`.

## 4 — Aggancio al programma (coordinato con Pezzo 4)

- `ProgrammaRequest`: campi `zona_tipo: ZonaTipo | None` e `zona_osm_id: str | None`
  (formato `"way/123"` / `"relation/456"`) — se il Pezzo 4 li ha già, verifica solo;
- `run_programma`: se `zona_osm_id` presente, risolvi la zona via core client e
  **inietta nome + centroide + bbox nel task del fan-out** (gli specialisti non
  rifanno il lookup).

## 5 — Frontend (pagina `/territorio` del Pezzo 5)

Selettore in testa alla pagina: autocomplete comune (`/territorio/comuni`) → chip
`zona_tipo` (opzionale) → mappa Leaflet (riuso infra `app/mappa/`) con candidati +
lista laterale → selezione → `zona_tipo`+`zona_osm_id` nella request. Fallback:
banner "analisi a livello comunale" + campo `zona` testuale. R6: niente `app/api/*`,
tutto via `apiFetch`.

## Vincoli

- Nessuna dipendenza nuova nel core se l'assemblaggio in puro Python regge (shapely
  solo se la discovery dimostra che serve — motivalo).
- R1 build context root se tocchi Dockerfile/compose (non dovrebbe servire).
- R12 `make lint && make test`; R3 test via `/tmp/oda-venv`.

## Test

- `overpass_to_features` su fixture reali (3 casi); `list_zones` con Overpass mockato
  (pytest-httpx) incluso fallback Nominatim e lista vuota; tool MCP con
  `sources`/`source_url`; endpoint con core mockato + cache hit; UI build verde.

## Output atteso

`zones.py` + helper GeoJSON + 3 tool MCP + `routers/territorio.py` + selettore zona
in `/territorio`; test verdi. Smoke: comune pugliese reale → zone industriali con
nomi veri → selezione → `POST /programma` che cita la zona OSM. Riepiloga la
discovery per aggiornare la spec.
