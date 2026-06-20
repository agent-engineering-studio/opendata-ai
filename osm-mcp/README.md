# OSM MCP Server — da coordinate a mappa interattiva, via agente AI

Geocoding, punti di interesse, routing e profili territoriali di OpenStreetMap,
esposti come strumenti MCP. In più, il pezzo che chiude il cerchio: trasforma un
GeoJSON in una **pagina HTML Leaflet+OSM self-contained**, pronta da aprire o da
mostrare inline in un client compatibile.

Un agente AI può così partire da un indirizzo, scoprire cosa c'è intorno,
calcolare un percorso e restituire una mappa navigabile — senza scrivere una
riga di JavaScript. Fa parte di **opendata-ai**, accanto ai server MCP per CKAN
e SDMX (ISTAT/Eurostat/OECD).

## Cosa fa

- **Geocoding** indirizzo ⇄ coordinate via **Nominatim** (diretto e inverso).
- **POI & contesto**: ricerca punti di interesse per categoria intorno a un
  punto o dentro un bounding box, digest di quartiere, colonnine di ricarica EV
  — via **Overpass**.
- **Routing** punto-punto e confronto modalità (auto/piedi/bici) via **OSRM**,
  con punto d'incontro equo tra più persone.
- **Zone territoriali**: risoluzione comune → codice ISTAT dal confine OSM,
  elenco/geometria delle zone (industriale, commerciale, centro storico…) e
  profili sintetici commercio / turismo / trasporto pubblico.
- **Rendering mappe**: GeoJSON → HTML Leaflet+OSM self-contained, singolo o
  multi-layer, anche a partire da un payload in stile agente CKAN.

Tutto stateless e deterministico; il rendering **non** coinvolge alcun LLM.

## Strumenti MCP

### Geocoding & routing

| Tool | Cosa fa | Argomenti chiave |
|---|---|---|
| `geocode_address` | Indirizzo / nome luogo → coordinate | `address`, `limit=5` |
| `reverse_geocode` | Coordinate → indirizzo strutturato | `lat`, `lon`, `zoom=18` |
| `get_route` | Percorso tra due punti (geometria + tappe) | `start_lat`, `start_lon`, `end_lat`, `end_lon`, `profile="driving"`, `steps=True` |
| `analyze_commute` | Confronto tempi auto / piedi / bici | `home_lat`, `home_lon`, `work_lat`, `work_lon` |
| `suggest_meeting_point` | Punto d'incontro che minimizza il tempo peggiore tra N persone | `points` (lista `[lat, lon]`), `profile="driving"` |

### POI & contesto

| Tool | Cosa fa | Argomenti chiave |
|---|---|---|
| `find_nearby_places` | POI per categoria entro un raggio | `lat`, `lon`, `radius_m=1000`, `category="restaurant"`, `limit=20` |
| `search_category_in_bbox` | POI di una categoria dentro un bounding box | `south`, `west`, `north`, `east`, `category`, `limit=50` |
| `explore_area` | Digest di quartiere: top POI per categorie comuni | `lat`, `lon`, `radius_m=800` |
| `find_ev_charging_stations` | Colonnine EV con connettore/potenza quando taggati | `lat`, `lon`, `radius_m=5000`, `limit=30` |
| `osm_health` | Ping a Nominatim / Overpass / OSRM e stato `healthy`/`degraded` | — |

### Zone territoriali (comuni / profili)

| Tool | Cosa fa | Argomenti chiave |
|---|---|---|
| `osm_lookup_comune` | Nome comune → codice `ref:ISTAT` zero-padded dal confine `admin_level=8` | `nome`, `limit=8` |
| `osm_list_zones` | Elenca zone OSM di un tipo dentro un comune (senza geometrie) | `cod_comune`, `zona_tipo`, `comune_nome=None` |
| `osm_get_zone` | Feature GeoJSON completa di una zona per id OSM | `osm_type` (way/relation/node), `osm_id` |
| `osm_commercial_profile` | Densità commerciale: conteggi POI per categoria (lente commercio/DUC) | `lat`/`lon`+`radius_m=1500` **oppure** `south/west/north/east` |
| `osm_tourism_profile` | Profilo turismo/cultura: conteggi asset + landmark nominati | `lat`/`lon`+`radius_m=3000` **oppure** bbox, `landmarks_limit=25` |
| `osm_transport_profile` | Profilo trasporto pubblico: conteggio nodi transit + presenza stazione | `lat`/`lon`+`radius_m=3000` **oppure** bbox |

`zona_tipo` ∈ `industriale | commerciale | portuale | centro_storico | verde |
agricola | quartieri`. I profili accettano **punto+raggio** oppure un **bbox**
(es. dalle zone di `osm_list_zones` o dal geocoding); restituiscono solo
conteggi (`out count`) — economici e completi — con blocco `sources` ODbL e
`source_url` citabile.

### Rendering mappe

| Tool | Cosa fa | Argomenti chiave |
|---|---|---|
| `render_geojson_map` | GeoJSON (Feature/FeatureCollection/Geometry) → HTML Leaflet single-layer | `geojson`, `title=None`, `center=None`, `zoom=None` |
| `render_multi_layer_map` | Più layer GeoJSON, ognuno con nome e stile (colori auto) | `layers` (lista `{name, geojson, style?}`), `title`, `center`, `zoom` |
| `compose_map_from_resources` | Payload in stile agente CKAN (testo + risorse con GeoJSON) → mappa multi-layer | `text`, `resources`, `title`, `center`, `zoom` |

I tre tool di rendering restituiscono multi-content: un sommario testuale + una
risorsa HTML (`mimeType=text/html`) che i viewer compatibili (Claude Desktop,
VS Code MCP) mostrano inline.

## Avvio rapido

Installazione editabile (lo stack condivide `opendata-core`):

```bash
cd osm-mcp && pip install -e ".[dev]"
```

**stdio** (default — per Claude Desktop / agenti locali):

```bash
MCP_TRANSPORT=stdio osm-mcp
```

**streamable-HTTP** (preferito per i client HTTP; endpoint `/mcp`):

```bash
MCP_TRANSPORT=streamable-http \
MCP_HOST=0.0.0.0 MCP_PORT=8080 \
osm-mcp                       # → http://localhost:8080/mcp
```

Variabili d'ambiente principali:

| Env | Default | Note |
|---|---|---|
| `MCP_TRANSPORT` | `stdio` | `stdio` \| `sse` \| `streamable-http` |
| `MCP_HOST` / `MCP_PORT` | `0.0.0.0` / `8080` | bind per i transport HTTP; endpoint `/mcp` |
| `OVERPASS_URL` | `https://overpass-api.de/api/interpreter` | endpoint Overpass primario |
| `OVERPASS_FALLBACK_URLS` | `https://overpass.kumi.systems/api/interpreter` | comma-separated, in rotazione con backoff + cache TTL 24h |
| `NOMINATIM_URL` | `https://nominatim.openstreetmap.org` | geocoding |
| `OSRM_URL` | `https://router.project-osrm.org` | routing |
| `OSM_USER_AGENT` / `OSM_CONTACT_EMAIL` | — | identificazione richiesta dalle usage policy |

> **Mirror Overpass.** I default upstream (`overpass-api.de`, `kumi.systems`)
> sono spesso **bloccati in egress** o throttlano (429). Nel compose del repo
> sono già puntati su mirror raggiungibili — FR (primario) + CH (fallback):
>
> ```yaml
> OVERPASS_URL: https://overpass.openstreetmap.fr/api/interpreter
> OVERPASS_FALLBACK_URLS: https://overpass.osm.ch/api/interpreter
> ```
>
> In produzione lo stack include anche un servizio `overpass` self-hosted
> (estratto Italia): basta puntargli le stesse env, nessuna modifica al codice.
> Dettagli operativi: `infra/overpass/README.md`.

## Usalo con un client MCP

**Claude Desktop** (`claude_desktop_config.json`), transport stdio:

```json
{
  "mcpServers": {
    "openstreetmap": {
      "command": "osm-mcp",
      "env": {
        "MCP_TRANSPORT": "stdio",
        "OVERPASS_URL": "https://overpass.openstreetmap.fr/api/interpreter",
        "OVERPASS_FALLBACK_URLS": "https://overpass.osm.ch/api/interpreter",
        "OSM_USER_AGENT": "opendata-ai/0.1 (you@example.com)"
      }
    }
  }
}
```

Per client HTTP (VS Code MCP, agenti che usano lo streamable-HTTP transport),
avvia con `MCP_TRANSPORT=streamable-http` e punta il client a
`http://<host>:8080/mcp`.

## Esempio

Dal nome di un luogo a una mappa interattiva, in tre passi:

1. **Geocoding** — `geocode_address(address="Piazza del Plebiscito, Napoli")`
   → `lat=40.8359`, `lon=14.2488`.
2. **Contesto** — `find_nearby_places(lat=40.8359, lon=14.2488, radius_m=600,
   category="restaurant", limit=20)` → elenco POI con nome, coordinate,
   orari e tag.
3. **Mappa** — costruisci una `FeatureCollection` con i POI trovati e chiama
   `render_geojson_map(geojson=..., title="Ristoranti vicino Plebiscito")` →
   ricevi una pagina HTML Leaflet+OSM self-contained, da aprire nel browser o
   da mostrare inline nel client.

Per il territorio: `osm_lookup_comune(nome="Gioia del Colle")` → `ref_istat
072021`, poi `osm_transport_profile(...)` / `osm_commercial_profile(...)` per i
conteggi citabili, e `osm_get_zone(...)` per la geometria da disegnare.

## 📣 Per i social

> Geocoding, POI, routing e zone territoriali di #OpenStreetMap, ora come
> strumenti #MCP. Un agente AI parte da un indirizzo, scopre cosa c'è intorno,
> calcola il percorso e restituisce una **mappa Leaflet interattiva
> self-contained** — dai dati geografici a una mappa navigabile, senza scrivere
> JavaScript. Open source, dati OSM sotto ODbL, parte del progetto opendata-ai.
>
> #GIS #geospatial #AI #opendata #LLM #OSM

## Licenza & note

I dati geografici provengono da **OpenStreetMap** e sono distribuiti sotto
**Open Database License (ODbL)** — © OpenStreetMap contributors. Le risposte dei
tool territoriali includono un blocco `sources` con l'attribuzione ODbL e una
`source_url` citabile per entità: riportala in qualsiasi mappa o report
derivato. Rispetta le usage policy delle istanze pubbliche di Nominatim,
Overpass e OSRM (identificati con `OSM_USER_AGENT` / `OSM_CONTACT_EMAIL`) e
preferisci mirror raggiungibili o istanze self-hosted per i carichi reali.
