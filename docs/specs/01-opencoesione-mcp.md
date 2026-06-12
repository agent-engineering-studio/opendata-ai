# Spec 01 — `opencoesione` core client + `opencoesione-mcp-server`

**Pezzo 1.** Nuova fonte dati OpenCoesione (progetti di politica di coesione
finanziati in Italia), aggiunta seguendo le convenzioni esistenti del repo:
client async in `opendata_core/`, wrapper FastMCP gemello di `istat-mcp-server` /
`ckan-mcp-server`. **Non** introduce nuovi pattern.

## Perché (verticale PA "Programma Evidence-Based")

Sblocca il caso d'uso "supporto al sindaco/amministratore": dato un comune o una
zona, sapere **quali progetti pubblici insistono sul territorio, quanto sono stati
finanziati e quanto effettivamente spesi**. Il valore distintivo non è elencare i
progetti ma calcolare la **capacità attuativa storica** (spend ratio) del comune:
un indicatore onesto di fattibilità che separa un programma serio dalle promesse.
OpenCoesione è la fonte naturale perché copre anagrafica, dati finanziari,
procedurali e fisici dei progetti, navigabili fino a livello comunale.

L'aggancio al fan-out dell'orchestratore (`OPENCOESIONE_INSTRUCTIONS` in
`opendata_backend/config.py` + branch nel parser, contratto `<!--RESOURCES_JSON-->`)
è il **Pezzo 2** e segue la regola R5 del `CLAUDE.md`. Questo pezzo si ferma al
client + MCP server, testabili in isolamento.

## Fonte dati

- **Base API**: `https://opencoesione.gov.it/it/api`
- **Formato**: JSON aggiungendo `.json` alla risorsa (es. `…/api/progetti.json`).
- **Risorse**: `progetti`, `soggetti`, `aggregati`.
- **Filtri territoriali**: per codice ISTAT (regione/provincia/comune) → join con `istat-mcp-server`.
- **Licenza**: dati API CC BY-SA 3.0; dataset bulk CC BY 4.0. Va riportata negli output.
- **Cicli**: 2007-2013, 2014-2020, 2021-2027.

> ⚠️ **Discovery obbligatoria (fase 0 del prompt).** L'API HTML auto-documenta, per
> ogni risorsa, filtri/ordinamenti e i **nomi esatti dei parametri di query**. Non
> assumerli: interrogare l'API live e mappare i campi reali. Questa spec descrive il
> comportamento atteso, non le stringhe-parametro esatte.

### Esiti discovery (eseguita 2026-06-12 — vedi `mapping.py` e README per il dettaglio)

Divergenze dalla spec originale, verificate sul vivo:

- Il root `/it/api/` è **JSON puro** (non HTML): risorse `progetti, soggetti,
  aggregati, temi, nature, territori, programmi` + `data_aggiornamento`.
- **I parametri sconosciuti sono ignorati in silenzio** (`cod_comune=` su /progetti
  ritorna il count totale!) → il client whitelist-a ogni filtro e valida gli slug
  client-side con errori actionable.
- Il filtro territoriale è per **slug** (`territorio=bari-comune`), non per codice
  ISTAT. La risoluzione codice→slug passa da `/territori` (`cod_com=72006`, interi
  senza zeri iniziali). Il join ISTAT della spec funziona, ma mediato dagli slug.
- I **cicli sono 4** (c'è anche `2000_2006`); il parametro è
  `ciclo_programmazione=2014_2020`.
- `/aggregati/territori/{slug}.json` include popolazione, totali e breakdown per
  stato/tema/natura/anno **e accetta `ciclo_programmazione`** → `funding_capacity`
  costa **una sola chiamata** (niente paginazione di 500 progetti come ipotizzato).
- `/soggetti` non supporta la ricerca per denominazione; filtri reali:
  territorio/tema/natura/ruolo.
- `page_size` cappato server-side a 500; **throttling aggressivo** (HTTP 429 con
  `detail` che suggerisce i secondi di attesa) → retry con backoff suggerito +
  cache TTL 1h.
- Importi in formato italiano (`"421465927,95"`), date `YYYYMMDD`.
- Aggiunto un 6° tool statico `opencoesione_reference_values` (slug validi di
  temi/nature/stati/cicli) per mitigare il footgun dei parametri ignorati.
- I tool restituiscono **dict strutturati** (convenzione reale degli altri server
  del repo: niente `response_format` markdown/json, che la spec ipotizzava).

## Layer 1 — core client (`opendata_core`)

Nuovo subpackage `opendata_core/src/opendata_core/opencoesione/`, stessa forma di
`ckan/`, `sdmx/`, `osm/`. **Nessun FastMCP, nessun LLM, nessun FastAPI.**

```
opendata_core/src/opendata_core/opencoesione/
  __init__.py        # esporta OpenCoesioneClient
  client.py          # httpx.AsyncClient async, retry/backoff, cache TTL (cachetools)
  models.py          # dataclass/Pydantic dei record (progetto, soggetto, aggregato)
  mapping.py         # enum tema/natura/stato + nomi-parametro scoperti in discovery
```

`OpenCoesioneClient` espone metodi async puri (ritornano dati strutturati, non testo):
`search_projects(...)`, `get_project(clp)`, `territorial_aggregates(...)`,
`search_soggetti(...)`. La logica di aggregazione per la capacità di spesa vive qui
come metodo `funding_capacity(cod_comune, tema=None, ciclo=None)` → riusabile anche
dal backend senza passare dall'MCP.

## Layer 2 — MCP wrapper (`opencoesione-mcp-server`)

Gemello di `istat-mcp-server`. Wrapper sottile: traduce input MCP → chiamate al
core client → output formattato (markdown/json) con blocco `sources`.

```
opencoesione-mcp-server/
  .dockerignore
  Dockerfile             # build context = repo ROOT (R1), copia opendata_core + sorgenti
  README.md
  pyproject.toml         # name "opencoesione-mcp-server", dep opendata-core, mcp, httpx, pydantic, cachetools
  src/opencoesione_mcp/
    __init__.py
    server.py            # FastMCP("opencoesione-mcp-server"), TRANSPORT switch, /healthz, register_tools
    tools.py             # register_tools(mcp): i 5 tool con prefisso opencoesione_
  tests/
    test_tools.py        # pytest + pytest-httpx (mock API)
```

### Tool (prefisso `opencoesione_`, tutti read-only)

| tool | scopo |
|---|---|
| `opencoesione_search_projects` | progetti filtrabili per comune/provincia/regione ISTAT, tema, ciclo, natura, stato, min_importo; paginato (`limit`/`offset`, `total`/`has_more`/`next_offset`) |
| `opencoesione_get_project` | dettaglio per codice locale progetto (CLP) |
| `opencoesione_territorial_aggregates` | risorse programmate/allocate/spese per territorio (+ tema) |
| `opencoesione_search_soggetti` | soggetti per query/ruolo/territorio |
| `opencoesione_funding_capacity` | **workflow tool**: spend ratio = pagato/finanziato + progetti conclusi/totali → capacità attuativa storica |

- `response_format`: `markdown` (default) | `json`, come gli altri server.
- Annotations: `readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true`, `openWorldHint: true`.
- Ogni output include blocco `sources` (URL risolvibile + data estrazione + licenza).
- Error handling actionable: 404 → "verifica il codice ISTAT"; 429 → backoff; timeout → ritenta.

## Integrazione stack (allineata al CLAUDE.md)

- **server.py**: stessa forma di istat — `TRANSPORT` env (`stdio` default | `streamable-http` | `sse`), `HOST`/`PORT=8080`/`MCP_PATH=/mcp`, `FastMCP(name="opencoesione-mcp-server", instructions=...)`, route `/healthz`, `register_tools(mcp)`, `[project.scripts] opencoesione-mcp-server = "opencoesione_mcp.server:main"`.
- **Dockerfile**: build context repo root, copia `opendata_core/` + `opencoesione-mcp-server/src` affiancati (R1).
- **docker-compose.yml**: nuovo servizio `opencoesione-mcp` (porta interna `:8080/mcp`); env `OPENCOESIONE_MCP_URL=http://opencoesione-mcp:8080/mcp` (interno) / `http://localhost:<port>/mcp` (host-debug) (R9).
- **Makefile**: target `make mcp-stdio-opencoesione` (one-shot `tools/list` su stdio), come gli altri.
- **CI**: `ci.yml` + `docker-publish.yml` raccolgono il nuovo package automaticamente se segue il pattern; verificare la matrice.
- **Test**: via `/tmp/oda-venv/bin/python -m pytest -q opencoesione-mcp-server` (R3). Prima del commit `make lint && make test` (R12).

## Definition of Done

- [ ] Core client in `opendata_core/opencoesione/` con metodi async puri + `funding_capacity`.
- [ ] Discovery completata; nomi-parametro reali in `mapping.py` + sezione "API Notes" nel README.
- [ ] 5 tool nel wrapper, prefisso `opencoesione_`, annotations + docstring + `sources`.
- [ ] `server.py` con TRANSPORT switch e `/healthz` identici per forma a istat.
- [ ] Dockerfile build context = repo root; servizio compose + env var aggiunti.
- [ ] `funding_capacity` verificato su un comune pugliese reale con numeri controllabili.
- [ ] `make mcp-stdio-opencoesione` elenca i 5 tool; `make lint && make test` verdi.
- [ ] README con setup, API Notes e nota licenza.
