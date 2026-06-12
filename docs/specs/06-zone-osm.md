# Spec 06 — Selezione zona via tag OSM (zone riconosciute)

**Pezzo 6 (riscritto).** Sostituisce il precedente approccio "disegna il poligono +
PostGIS" (archiviato in `deferred/06-confini-postgis.md`). La zona di analisi non si
disegna a mano libera: si **seleziona tra entità OSM riconosciute** (zone industriali,
aree commerciali, porto, centro storico…) trovate via tag dentro il comune scelto.
Zero infrastruttura nuova: niente PostGIS, niente tabella confini, niente MCP server
nuovo — solo Overpass/Nominatim, già usati da `opendata_core/osm/`.

## Perché il cambio di approccio

- **Provenienza.** Un poligono a mano libera non ha fonte; un'entità OSM ha nome,
  `osm_id` stabile, URL citabile (`https://www.openstreetmap.org/way|relation/<id>`)
  e licenza ODbL. Coerente con il modello evidence-based del Pezzo 4: la zona stessa
  diventa una risorsa citabile.
- **Niente risoluzione spaziale.** I confini comunali italiani su OSM portano
  `ref:ISTAT` sugli `admin_level=8`: l'ancoraggio comune → zone è una query Overpass
  con filtro ad area. Il `cod_comune` per i join OpenCoesione/ISTAT arriva dalla
  scelta del comune a monte — la risoluzione poligono → comune (l'unica vera ragione
  d'essere di PostGIS) non serve più nel percorso principale.
- **UX migliore.** "Scegli tra le 3 zone industriali del tuo comune" batte "disegna
  un poligono e speriamo".

## Discovery obbligatoria (fase 0 del prompt)

Come per OpenCoesione/ISPRA: **non assumere, interrogare**. Su 3–4 comuni campione
pugliesi (di taglia diversa) verificare con query Overpass reali:

1. copertura di `ref:ISTAT` sugli `admin_level=8` (attesa: completa in Italia);
2. resa per ogni `zona_tipo` della tassonomia (quanti poligoni, con/senza `name`);
3. almeno un caso di **centro storico non mappato**, per validare la catena di
   fallback;
4. forma reale delle relation multipolygon restituite da `out geom` (ruoli
   outer/inner) per dimensionare l'helper di assemblaggio GeoJSON.

Annotare i risultati in `mapping.py` (core) e nella sezione "API Notes" del README di
`osm-mcp`.

## Tassonomia `zona_tipo` → tag OSM

| `zona_tipo` | Filtri Overpass (way + relation) | Note copertura |
|---|---|---|
| `industriale` | `landuse=industrial`; `man_made=works` | molto buona |
| `commerciale` | `landuse=retail`, `landuse=commercial` | buona |
| `portuale` | `landuse=harbour`, `industrial=port` | buona dove esiste |
| `centro_storico` | `place=quarter/suburb/neighbourhood` con `name~"centro storico",i`; `boundary=administrative` `admin_level=10` con nome analogo | **disomogenea** → fallback |
| `verde` | `leisure=park`, `boundary=protected_area` | buona |
| `agricola` | `landuse=farmland`, `landuse=orchard`, `landuse=vineyard` | mappata ma frammentata (molti poligoni piccoli) |

La tassonomia è un **enum condiviso** (`ZonaTipo`) definito nel core client e
riusato dal backend (Pezzo 4: `ProgrammaRequest.zona_tipo`) e dalla UI. La mappa
tipo→tag vive in un solo posto: `opendata_core/osm/zones.py`.

## Catena di fallback (sempre dichiarata all'utente)

1. **Tag match** → poligoni candidati con nome e osm_id (caso ideale).
2. **Nominatim** su `"<zona_tipo label> <comune>"` (es. "centro storico Bari") via il
   `geocode()` esistente → se ritorna un'area nominata, usarla (provenienza: URL
   Nominatim/OSM).
3. **Nessuna geometria** → si degrada al comportamento del Pezzo 4 senza zona:
   analisi a livello comune con `zona` testuale. Il sistema **non si rompe mai, al
   peggio perde granularità — e lo dice** (campo `fallback_level` nella risposta,
   nota in UI).

## 6A — Core client (`opendata_core/osm/`)

Nuovo modulo `zones.py` + estensioni a `client.py`/`geojson.py`. DB-free, nessuna
dipendenza nuova (assemblaggio multipoligono in puro Python; shapely solo se la
discovery dimostra che serve).

- `lookup_comune(nome: str) -> list[ComuneMatch]` — query Overpass su
  `boundary=administrative` + `admin_level=8` + `name` (case-insensitive), ritorna
  `{nome, ref_istat, cod_provincia?, osm_id}`. Serve all'autocomplete UI e a chi non
  conosce il codice ISTAT.
- `list_zones(ref_istat: str, zona_tipo: ZonaTipo) -> list[ZoneCandidate]` — query
  Overpass con filtro ad area:

  ```
  [out:json][timeout:30];
  area["boundary"="administrative"]["admin_level"="8"]["ref:ISTAT"="<ref>"]->.a;
  ( way[<tag>](area.a); relation[<tag>](area.a); );
  out geom tags;
  ```

  Ogni candidato: `{osm_type, osm_id, name?, zona_tipo, area_m2 (approssimata),
  centroid, bbox, osm_url}`. I poligoni senza `name` restano selezionabili
  ("Zona industriale senza nome #2") ma ordinati dopo quelli nominati e per area
  decrescente.
- `get_zone(osm_type: str, osm_id: int) -> Feature` — geometria completa GeoJSON.
- `geojson.py`: helper `overpass_to_features(elements)` — way chiusi → Polygon;
  relation multipolygon → assemblaggio ring outer/inner. È l'unico pezzo non banale:
  testarlo con fixture JSON Overpass reali salvate dalla discovery.
- Cache TTL (`cachetools`, pattern del repo): le zone di un comune cambiano raramente.
- Rispettare il rate limit dell'istanza Overpass configurata (`OVERPASS_URL` in
  `OsmSettings` esiste già); un solo retry con backoff su 429/504.

## 6B — Tool MCP (in `osm-mcp`, nessun server nuovo)

Tre tool nuovi accanto a geocode/POI/routing esistenti, prefisso `osm_`:

| tool | scopo |
|---|---|
| `osm_lookup_comune(nome)` | nome → candidati `{nome, ref_istat}` |
| `osm_list_zones(cod_comune, zona_tipo)` | candidati zona (nome, tipo, area, centroide, bbox, osm_url) — applica la catena di fallback e dichiara il livello usato |
| `osm_get_zone(osm_type, osm_id)` | GeoJSON completo della zona |

- `response_format` markdown/json come gli altri; annotations read-only/idempotent.
- Blocco `sources` con attribuzione **ODbL © OpenStreetMap contributors** + URL
  dell'entità + timestamp.
- Ogni risultato include `source_url` (contratto cattura citazioni del synth, come
  Pezzo 2).

## 6C — Endpoint backend per la UI (`routers/territorio.py`)

L'agente usa l'MCP (R13); la **UI non parla con gli MCP**. Il backend importa
direttamente `opendata_core.osm` (è la shared lib — nessun hop MCP):

- `GET /territorio/comuni?q=<nome>` → lookup comune (autocomplete).
- `GET /territorio/zone?cod_comune=<istat>&tipo=<zona_tipo>` → candidati con
  geometrie GeoJSON + `fallback_level`.
- Entrambi `Depends(enforce_rate_limit)` (R7, mai anonimi), registrati in `main.py`.
- **Cache Redis** (TTL 24h, chiave `(cod_comune, tipo)`): protegge Overpass dal
  traffico UI ripetuto.

### Uso della zona nel programma (aggancio al Pezzo 4)

`ProgrammaRequest` guadagna `zona_tipo` e `zona_osm_id` (vedi spec 04 aggiornata).
Quando `zona_osm_id` è presente, `run_programma` risolve la zona via core client e
**inietta nome + centroide + bbox nel task del fan-out**: lo specialista OSM (Pezzo
7a) parte dal centroide per le distanze/POI, ISPRA (Pezzo 7b) usa il bbox per i
layer WFS. Nessun partecipante deve rifare il lookup.

## 6D — Frontend (sulla pagina `/territorio`, Pezzo 5)

Flusso di selezione in testa alla pagina:

1. autocomplete comune (`GET /territorio/comuni?q=`) → `cod_comune`;
2. chip dei `zona_tipo` (Industriale / Commerciale / Portuale / Centro storico /
   Verde / Agricola) — opzionale: senza tipo, analisi a livello comune;
3. mappa Leaflet (riuso infra `app/mappa/`) con i candidati evidenziati + lista
   laterale (nome, area) → click = selezione → `zona_tipo` + `zona_osm_id` nella
   `ProgrammaRequest`;
4. fallback dichiarato: nessuna zona trovata → banner "analisi a livello comunale" +
   campo `zona` testuale (comportamento Pezzo 5 base).

Vincoli soliti: static export, `apiFetch` con token, nessun `app/api/*` (R6).

## Fuori scope / appendice PostGIS

La vecchia spec (`deferred/06-confini-postgis.md`) torna utile **solo** se/quando
serviranno: intersezione sotto-comunale dei progetti con coordinate puntuali, zone a
cavallo di più comuni, o analisi su poligoni arbitrari. Non è prerequisito di nulla
nella roadmap attuale.

## Definition of Done

- [ ] Discovery completata su 3–4 comuni campione; esiti in `zones.py`/README.
- [ ] Core: `ZonaTipo`, `lookup_comune`, `list_zones`, `get_zone`,
      `overpass_to_features` con test su fixture Overpass reali (way chiuso,
      multipolygon con inner, elemento senza nome).
- [ ] 3 tool MCP in `osm-mcp` con `sources` ODbL + `source_url`; fallback chain con
      `fallback_level` dichiarato; `make mcp-stdio-osm` li elenca.
- [ ] `routers/territorio.py`: 2 endpoint auth+rate-limit, cache Redis, registrati in
      `main.py`; test (mock core client).
- [ ] `ProgrammaRequest.zona_tipo/zona_osm_id` consumati da `run_programma`
      (iniezione nome/centroide/bbox nel task) — coordinato con spec 04.
- [ ] UI: autocomplete comune → chip tipo → mappa candidati → selezione → scheda;
      fallback con banner. `next build` verde.
- [ ] `make lint && make test` verdi (R12).
- [ ] Smoke: comune pugliese reale → zone industriali elencate con nomi veri →
      selezione → `POST /programma` con la zona → scheda che cita la zona OSM.
