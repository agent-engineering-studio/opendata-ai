# Prompt Claude Code — P07b: fonte ISPRA (dissesto + consumo di suolo)

> Eseguire dalla root di `opendata-ai`, dopo i Pezzi 1–6 e P07a. Leggi `CLAUDE.md`
> (R1, R5, R13) e `docs/specs/07-arricchimento-osm-ispra.md` §7B. È un'altra fonte
> nuova: ripeti il pattern **Pezzo 1 (core+mcp) + Pezzo 2 (wiring)** per ISPRA.

---

Aggiungi **ISPRA** come fonte di **vincoli ambientali** a livello comunale: rischio
idrogeologico (IdroGEO: indicatori di pericolosità frane/alluvioni, esposti) e
**consumo di suolo**. Alimenta SWOT "minacce/vincoli" e la fattibilità del programma.

## Fase 0 — Discovery (NON saltare)

Interroga le fonti reali e mappa endpoint/parametri (non assumerli):
1. **IdroGEO** (ISPRA): individua l'**API REST** e i servizi **WMS/WFS** (IFFI,
   mosaicature pericolosità frane/alluvioni, indicatori di rischio). Trova come si
   ottengono gli **indicatori per `cod_comune`** (% area/popolazione/edifici/imprese
   esposti). Parti da `https://idrogeo.isprambiente.it` (app open source) e dalla sua
   pagina open-data.
2. **Consumo di suolo** ISPRA: individua tabelle comunali / WFS dell'edizione annuale.
   Verifica cosa è già su `geodati.gov.it`/`dati.gov.it` (CKAN) per **non duplicare**
   ciò che il `ckan-mcp` raggiunge già.
3. Scrivi gli endpoint/layer/parametri reali in `opendata_core/ispra/mapping.py` e in
   "API Notes" del README. Licenza **CC BY-SA 3.0 IT** (citazione ISPRA obbligatoria).

## Layer 1 — core client

`opendata_core/src/opendata_core/ispra/` (DB-free, come `sdmx/`/`opencoesione/`):
`IspraClient` async (httpx, retry/backoff, cache TTL) con metodi puri:
`risk_indicators(cod_comune)`, `soil_consumption(cod_comune)`, e (opz.)
`landslide_features(comune|bbox)` da WFS. `models.py`, `mapping.py`, `__init__.py`.
Aggiorna `opendata_core/pyproject.toml` se servono dip. (probabilmente solo httpx già
presente; per il WFS valutare il parsing GeoJSON/GML).

## Layer 2 — MCP `ispra-mcp-server`

Clona `opencoesione-mcp-server`. Tool prefisso `ispra_`:
`ispra_risk_indicators(cod_comune)`, `ispra_soil_consumption(cod_comune)`,
(opz.) `ispra_landslide_features(...)`. Output markdown/json con blocco `sources`
(URL + CC BY-SA 3.0 IT). `server.py` con switch `TRANSPORT` + `/healthz`. `pyproject`
con `opendata-core`, `mcp`, `httpx`, `pydantic`, `cachetools`. Includi `source_url` in
ogni risultato (contratto per la cattura citazioni del synth). Tests con pytest-httpx.

## Layer 3 — wiring fan-out (come Pezzo 2)

1. `parsing.py`: `SourceTag` += `"ispra"`.
2. `config.py`: `ISPRA_INSTRUCTIONS` (per `cod_comune` ottieni rischio + consumo di
   suolo; emetti citazioni `source:"ispra"`); `Settings`: `enable_ispra`,
   `ispra_mcp_url`, `ispra_agent_name="ispra"`; aggiorna `SYNTH_INSTRUCTIONS`.
3. `factory.py`: blocco partecipante ISPRA (come opencoesione, fuori da `sdmx_specs`).
4. `synth.py`: `_normalise_source_tag` += `ispra`; `_SYNTH_SOURCE_ORDER` += `ispra`;
   branch di cattura `source=="ispra"` (usa `source_url`).
5. **`PROGRAMMA_INSTRUCTIONS`** (Pezzo 4): una proposta su zona a pericolosità ISPRA
   elevata DEVE riportarlo come vincolo in `fattibilita.motivazione` (priorità messa in
   sicurezza prima dell'espansione). Integra i vincoli ambientali nella fattibilità.
6. `.env.*`: `ENABLE_ISPRA`, `ISPRA_MCP_URL`, `ISPRA_AGENT_NAME`.
7. `docker-compose.yml`: servizio `ispra-mcp`; `Makefile`: `make mcp-stdio-ispra`.

## Test e vincoli

- core/mcp: API mockata (risk_indicators/soil_consumption) + assenza dati gestita;
  wiring: `test_config.py`/`test_synth_merge.py` estesi.
- R1 build context root; R13 dati via MCP; R5 aggiorna insieme le fonti di verità;
  R12 `make lint && make test`.

## Output atteso

`opendata_core/ispra/` + `ispra-mcp-server` + wiring completo + integrazione nella
fattibilità del programma; env/compose/Makefile; test verdi. Smoke: `POST /programma`
su un comune con area a pericolosità nota → la scheda riporta il vincolo idrogeologico
e il consumo di suolo, con fonti ISPRA risolvibili. Resoconto della discovery per
aggiornare la spec.
