# Example queries

Copy-pasteable example queries for **Esplora** — the conversational,
multi-source search of opendata-ai. Type any of these in the Esplora search box,
or send them to the backend:

```bash
curl -sX POST "$OPENDATA_API/datasets/search" \
  -H "Authorization: Bearer $OPENDATA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "stazioni di ricarica per veicoli elettrici in Lombardia"}'
```

(Set `prefer_geo: true` in the body when you want the map view — it biases the
fan-out toward geographic resources.)

All examples use **public** open data only. The intended source is indicated,
but the orchestrator fans out across sources and may enrich the answer from
others.

## CKAN portals (dati.gov.it, regional/municipal)

| Query | Source | You get |
|---|---|---|
| `stazioni di ricarica per veicoli elettrici in Lombardia` | CKAN (`dati.gov.it`) | table / chart — points you can also map |
| `prezzi medi dei carburanti per regione` | CKAN (`dati.gov.it`) | **tabular** CSV → preview + chart |
| `farmacie in provincia di Bari` | CKAN (regional) | table (address list) |
| `bilancio del Comune di Milano ultimo anno` | CKAN (`dati.comune.milano.it`) | tabular CSV → chart |

## ISTAT SDMX dataflows

| Query | Source | You get |
|---|---|---|
| `popolazione residente per regione 2019-2023` | ISTAT (SDMX) | **tabular** time series → chart |
| `tasso di disoccupazione per provincia` | ISTAT (SDMX) | table → **chart** (bar by province) |
| `imprese attive per settore ATECO in Puglia` | ISTAT ASIA (SDMX) | tabular → chart |

## Geographic resources (rendered on the map)

| Query | Source | You get |
|---|---|---|
| `confini amministrativi dei comuni della Puglia` | CKAN / RNDT (GeoJSON) | **map** — administrative boundaries |
| `piste ciclabili di Bologna` | CKAN (`dati.gov.it`) | **map** — GeoJSON line layer |
| `aree verdi del Comune di Torino` | CKAN (`aperto.comune.torino.it`) | **map** — polygon layer |

> Tip: add `prefer_geo: true` (API) or use the **Mappa** page (UI) so geographic
> formats (GeoJSON / Shapefile / KML) are preferred and rendered as map layers.

## Tabular resources (previewed and charted)

| Query | Source | You get |
|---|---|---|
| `numero di posti letto negli ospedali per regione` | ISTAT / Ministero Salute | **table** → chart |
| `spesa per la cultura dei comuni italiani` | CKAN (`dati.gov.it`) | **table** → chart by comune |

## What "map" vs "table/chart" means

- **Map** — the resource is a geographic format (GeoJSON, KML, SHP, ZIP): it is
  rendered as a toggleable Leaflet + OpenStreetMap layer.
- **Table** — tabular CSV/JSON (or SDMX-CSV from ISTAT): shown with detected
  rows/columns/types.
- **Chart** — the numeric columns of a table become selectable series, grouped
  by a dimension you choose.

See the [main README](../README.md) for the four product modes and the
[Esplora walkthrough](../README.md#1-esplora--esplorazione-conversazionale-dei-dati).
