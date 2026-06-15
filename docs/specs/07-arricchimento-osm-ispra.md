# Spec 07 — Arricchimento territoriale: OSM accessibilità + ISPRA rischio/suolo

**Pezzo 7.** Aggiunge due dimensioni alla SWOT del programma: **accessibilità** (OSM)
e **vincoli ambientali** (ISPRA: dissesto idrogeologico + consumo di suolo). Due
nature diverse:

- **7A — OSM**: i tool esistono già (`osm-mcp`, geocoding/POI/routing) ma **non sono
  agganciati al fan-out** (oggi OSM è usato solo per rendere le mappe via
  `attach_maps`). Qui lo promuoviamo a specialista, riusando le meccaniche del Pezzo 2.
- **7B — ISPRA**: fonte **nuova** → core client + MCP + wiring (come Pezzi 1+2), con
  discovery-first sugli endpoint reali.

Entrambe le fonti sono **keyed per comune ISTAT** → si innestano sul join esistente.

## 7A — OSM come specialista del fan-out

Contributo: accessibilità della zona — distanza da casello autostradale, stazione,
porto/aeroporto, e prossimità di servizi (POI). Utile per SWOT "forze/opportunità"
(logistica) o "debolezze" (isolamento).

Modifiche (sul modello esatto del Pezzo 2):
- `parsing.py`: `SourceTag` += `"osm"` (oltre a `"opencoesione"` del Pezzo 2).
- `config.py`: `OSM_INSTRUCTIONS` (l'agente geocoda il comune/zona, calcola distanze
  con i tool routing e cerca POI rilevanti; emette risorse/citazioni con
  `source: "osm"`); `Settings`: `enable_osm` (riusa `osm_mcp_url` già presente),
  `osm_agent_name`. Aggiorna `SYNTH_INSTRUCTIONS` per la sezione `=== OSM ===`.
  Se il task porta la zona risolta dal Pezzo 6 (`06-zone-osm.md`: nome + centroide +
  bbox iniettati da `run_programma`), l'agente parte dal **centroide** per
  distanze/POI invece di rigecodare.
- `factory.py`: blocco partecipante OSM (come CKAN/opencoesione, fuori da `sdmx_specs`).
- `synth.py`: `_normalise_source_tag` += `osm`; `_SYNTH_SOURCE_ORDER` += `osm`. La
  cattura di `preview_html`/GeoJSON OSM è **già** gestita dal synth e da `attach_maps`.
- `geo_filter.py`: verifica che le risorse OSM (già geo) non vengano scartate.
- `.env.*`: `ENABLE_OSM`, `OSM_AGENT_NAME`.

## 7B — ISPRA (dissesto + consumo di suolo): nuova fonte

### Capacità mirate (livello comunale)
- **IdroGEO / indicatori di rischio**: per `cod_comune`, % superficie e popolazione/
  edifici/imprese esposti a pericolosità da frana e alluvione (scenari). Alimenta SWOT
  "minacce/vincoli" e la fattibilità (un'area industriale in zona R3/R4 ha vincoli).
- **Consumo di suolo (ISPRA)**: % suolo consumato per comune e variazione annua.
  Alimenta "opportunità" (lotti liberi vs saturazione) e i vincoli di espansione.

### Fonti dati (discovery-first — non assumere gli endpoint)
- **IdroGEO** (ISPRA): piattaforma open data/open source con **API REST** e servizi
  **WMS/WFS** su IFFI, mosaicature di pericolosità frane/alluvioni e indicatori di
  rischio; supporta interrogazione per localizzazione/comune.
- **Consumo di suolo**: edizione annuale ISPRA, disponibile come tabelle comunali e
  servizi WFS/WMS; parte è anche su `geodati.gov.it` / `dati.gov.it` (CKAN → in parte
  già raggiungibile dal `ckan-mcp`, da non duplicare).
- **Licenza**: CC BY-SA 3.0 IT (citazione fonte ISPRA obbligatoria negli output).

> ⚠️ **Discovery (fase 0 del prompt)**: interrogare le API/WFS reali di IdroGEO e del
> consumo di suolo, mappare i nomi dei layer/endpoint/parametri e i codici comune, e
> scrivere `mapping.py`. Questa spec descrive il comportamento atteso, non le stringhe
> esatte.

### Layer (come le altre fonti)
- **Core client** `opendata_core/ispra/`: `IspraClient` async (httpx, retry/backoff,
  cache TTL), metodi puri: `risk_indicators(cod_comune)`, `landslide_features(bbox|comune)`
  (da WFS, opzionale), `soil_consumption(cod_comune)`. `models.py` + `mapping.py`.
  Il `bbox` per le query WFS può arrivare dalla **zona OSM** selezionata (Pezzo 6),
  iniettata nel task da `run_programma` — nessuna dipendenza da PostGIS.
- **MCP** `ispra-mcp-server/` (gemello di opencoesione): tool prefisso `ispra_`:
  `ispra_risk_indicators`, `ispra_soil_consumption`, e (opz.) `ispra_landslide_features`.
  Output con blocco `sources` (URL risolvibile + licenza CC BY-SA 3.0 IT). Transport
  stdio/streamable-http, `/healthz`.
- **Wiring fan-out** (come Pezzo 2): `SourceTag` += `"ispra"`; `ISPRA_INSTRUCTIONS` +
  `enable_ispra`/`ispra_mcp_url`/`ispra_agent_name` in `config.py`; blocco partecipante
  in `factory.py`; `_normalise_source_tag`/`_SYNTH_SOURCE_ORDER`/cattura citazioni in
  `synth.py`; `SYNTH_INSTRUCTIONS`/`PROGRAMMA_INSTRUCTIONS` aggiornati per integrare i
  vincoli ambientali nella fattibilità.

## Effetto sul programma (Pezzo 4)

`PROGRAMMA_INSTRUCTIONS` evolve: una proposta su una zona con pericolosità ISPRA
elevata **deve** segnalarlo come vincolo nella `fattibilita.motivazione` (es. "area in
classe di pericolosità frana elevata → priorità a messa in sicurezza prima di
espansione"). Questo rende le proposte realistiche, non solo finanziariamente ma
ambientalmente — coerente con la tua esperienza LandslideWatch.

## Esiti implementazione (2026-06-12)

**Discovery 7B** — divergenza maggiore: il **consumo di suolo ISPRA non ha
alcuna API REST** (solo tabelle comunali XLSX annuali e servizi cartografici;
i domini "esploradati.consumosuolo" ecc. non esistono) → fuori scope; parte
dei dataset resta raggiungibile via CKAN. IdroGEO invece è ottima:
`GET /api/pir/comuni/{uid}` (uid = codice ISTAT, zero-padded o intero), JSON
piatto con 134 chiavi (frane P4…AA + aggregato P3+P4, idraulica P3/P2/P1,
aree/percentuali e popolazione/famiglie/edifici/imprese/beni culturali
esposti). Una sola chiamata per comune, dato stabile → cache 24h.

**Implementazione** — `ispra_landslide_features` (WFS) non implementato
(opzionale in spec, non necessario al programma). Cattura citazioni
generalizzata in `synth.py`: il branch `source_url` ora copre
opencoesione/osm/ispra (`_citation_resource_from_payload`); i lookup (liste
candidati zone, resolve territorio) non diventano citazioni.

**Correzioni emerse dagli smoke con Ollama** (tre run sul caso reale
Barletta, pericolosità idraulica P3 13,9%):
1. il task portava solo il codice ISTAT e l'agente OSM geocodificava "zona
   industriale, Italia" finendo ad **Alessandria** → aggiunto
   `ProgrammaRequest.comune_nome` (la UI lo passa dalla selezione), iniettato
   nel task come "110002 (Barletta)";
2. citazioni duplicate da chiamate ripetute allo stesso tool → dedupe per URL
   anche intra-partecipante;
3. un typo del modello (`fonte: "ospr"`) invalidava l'INTERA scheda →
   `Evidenza.fonte` è `str` normalizzato (il guardrail vero è l'URL) e la
   validazione del JSON è per-voce (l'item malformato si scarta col log).

**Smoke finale (v3)**: scheda su Barletta con industrie reali (Buzzi Unicem,
TIMAC Agro) citate da OSM, voce [minacce] col rischio idraulico citato ISPRA,
e la proposta degradata a `da_verificare` con motivazione "priorità a messa
in sicurezza prima dell'espansione" — il comportamento chiesto da questa spec.
I 504/429 di Overpass pubblico degradano con grazia senza rompere la scheda.

## Definition of Done

- [ ] **7A**: OSM agganciato al fan-out (parsing/config/factory/synth/env); query "zona
      industriale" cita anche accessibilità con `source:"osm"`.
- [ ] **7B core+mcp**: `opendata_core/ispra/` + `ispra-mcp-server` con i tool, discovery
      completata, `mapping.py` documentato, `sources` con licenza CC BY-SA 3.0 IT.
- [ ] **7B wiring**: `SourceTag` += ispra; INSTRUCTIONS + Settings + factory + synth;
      `PROGRAMMA_INSTRUCTIONS` integra i vincoli ambientali nella fattibilità.
- [ ] `.env.*`, `docker-compose` (servizio `ispra-mcp`), `Makefile`
      (`make mcp-stdio-ispra`) aggiornati.
- [ ] Test: OSM partecipante finto taggato `osm`; ISPRA tool con API mockata
      (risk_indicators/soil_consumption); synth integra le nuove sezioni.
- [ ] `make lint && make test` verdi.
- [ ] Smoke: `POST /programma` su un comune pugliese con area a pericolosità nota →
      la scheda riporta il vincolo idrogeologico e l'accessibilità, con fonti
      ISPRA/OSM risolvibili.
