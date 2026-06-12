# Prompt Claude Code — P01: `opencoesione` core client + `opencoesione-mcp-server`

> Eseguire dalla root del repo `opendata-ai`. Leggi prima `CLAUDE.md` (invarianti
> di architettura e regole R1–R13) e `docs/specs/01-opencoesione-mcp.md` (contratto).
> Replica le convenzioni di `istat-mcp-server/` e `ckan-mcp-server/` — non inventare
> nuovi pattern.

---

Aggiungi la fonte dati **OpenCoesione** (`https://opencoesione.gov.it/it/api`) al
monorepo, in due layer come le fonti esistenti:

1. un **core client async** in `opendata_core/` (nessun FastMCP/LLM/FastAPI);
2. un **wrapper FastMCP** `opencoesione-mcp-server/`, gemello di `istat-mcp-server/`.

Studia `opendata_core/src/opendata_core/sdmx/` e `istat-mcp-server/src/istat_mcp/`
(`server.py`, `tools.py`, `pyproject.toml`, `Dockerfile`) e ricalcane forma e stile.

## Fase 0 — Discovery (NON saltare)

Interroga l'API live e scopri i **nomi reali dei parametri**, non assumerli:

1. Fetch `https://opencoesione.gov.it/it/api/progetti.json`; ispeziona lo schema di
   un progetto (codice locale CLP, campi finanziari finanziato/impegnato/pagato,
   localizzazione comunale, soggetti).
2. Naviga la versione HTML di `progetti`, `soggetti`, `aggregati` per leggere
   filtri/ordinamenti documentati e i nomi-stringa esatti dei parametri (filtro per
   codice comune ISTAT, per tema, per ciclo, ecc.).
3. Scarica un dettaglio progetto via CLP per mappare i campi del singolo record.
4. Scrivi quanto scoperto in `opendata_core/src/opendata_core/opencoesione/mapping.py`
   (enum tema/natura/stato, nomi parametri, mapping campi→modelli) e nella sezione
   "API Notes" del README del server. **Se la realtà diverge dalla spec, adatta il
   codice alla realtà e annotalo.** Non inventare endpoint o parametri.

## Layer 1 — core client

Crea `opendata_core/src/opendata_core/opencoesione/` con:
- `client.py` → `OpenCoesioneClient` su `httpx.AsyncClient`: base URL configurabile,
  timeout, **retry/backoff** su 429/5xx, **cache TTL** (`cachetools`, già dip. del
  repo). Una sola `_request()` interna riusata da tutti i metodi. Metodi async puri
  (ritornano dati strutturati): `search_projects(...)`, `get_project(clp)`,
  `territorial_aggregates(...)`, `search_soggetti(...)`, e
  `funding_capacity(cod_comune, tema=None, ciclo=None)` che pagina internamente i
  progetti (tetto di sicurezza es. 500), somma finanziato/pagato, calcola spend ratio
  e progetti conclusi/totali.
- `models.py` → modelli dei record (Pydantic v2 o dataclass, coerente con `sdmx/`).
- `mapping.py` → output della discovery.
- `__init__.py` → esporta `OpenCoesioneClient`.
Aggiorna `opendata_core/pyproject.toml` se servono nuove dipendenze (probabilmente no).

## Layer 2 — MCP wrapper

Crea `opencoesione-mcp-server/` clonando la struttura di `istat-mcp-server/`:
- `pyproject.toml`: `name = "opencoesione-mcp-server"`, `requires-python ">=3.11"`,
  dep `opendata-core>=0.1.0`, `mcp`, `httpx`, `pydantic`, `anyio`, `uvicorn[standard]`,
  `starlette`, `cachetools`; dev `pytest`, `pytest-asyncio`, `pytest-httpx`, `ruff`;
  `[project.scripts] opencoesione-mcp-server = "opencoesione_mcp.server:main"`;
  hatchling, ruff line-length 100, pytest asyncio_mode auto. **Copia il pyproject di
  istat e adatta i nomi.**
- `src/opencoesione_mcp/server.py`: identico per forma a quello di istat —
  `TRANSPORT` env (`stdio` default | `streamable-http` | `sse`),
  `HOST`/`PORT=8080`/`MCP_PATH=/mcp`, `FastMCP(name="opencoesione-mcp-server",
  instructions="...descrivi i 5 tool e il flusso tipico (cerca progetti → funding_capacity)...")`,
  route `/healthz`, `register_tools(mcp)`, `main()` con lo stesso switch transport.
- `src/opencoesione_mcp/tools.py`: `register_tools(mcp)` registra i 5 tool con
  `@mcp.tool(name=..., annotations={...})`, input Pydantic, docstring complete. I tool
  delegano al `OpenCoesioneClient` e formattano l'output (markdown/json) con un helper
  condiviso che aggiunge il blocco `sources` (URL + data + licenza). Prefisso
  `opencoesione_`:
  `opencoesione_search_projects`, `opencoesione_get_project`,
  `opencoesione_territorial_aggregates`, `opencoesione_search_soggetti`,
  `opencoesione_funding_capacity`. Annotations: tutti read-only, non distruttivi,
  idempotenti, `openWorldHint: true`.
- `Dockerfile`: copia quello di istat. **Build context = repo ROOT (R1)**: copia
  `opendata_core/` e `opencoesione-mcp-server/src` affiancati.
- `.dockerignore`, `README.md` (setup + API Notes dalla discovery + nota licenza).
- `tests/test_tools.py`: pytest + `pytest-httpx` mockando l'API; copri
  `search_projects`, `get_project`, e soprattutto `funding_capacity` (verifica il
  calcolo dello spend ratio su un payload finto noto).

## Wiring stack (senza toccare l'orchestratore — quello è il Pezzo 2)

- `docker-compose.yml`: aggiungi servizio `opencoesione-mcp` (porta interna
  `:8080/mcp`), sul modello del servizio istat. Aggiungi `OPENCOESIONE_MCP_URL` agli
  `.env.*.example` (interno `http://opencoesione-mcp:8080/mcp`, host-debug
  `http://localhost:<port>/mcp`) (R9).
- `Makefile`: aggiungi `make mcp-stdio-opencoesione` sul modello degli altri
  `mcp-stdio-*`.
- Verifica che `ci.yml` / `docker-publish.yml` includano il nuovo package (matrice).

## Vincoli (dal CLAUDE.md)

- R1 build context repo root. R3 test via `/tmp/oda-venv/bin/python -m pytest -q
  opencoesione-mcp-server`. R12 `make lint && make test` prima del commit, mai
  `--no-verify`. R13 questo è un **MCP server** (tool per l'LLM), non A2A.
- **NON** modificare ora `opendata_backend/` (config.py/parsing.py/factory.py):
  l'aggancio al fan-out è il Pezzo 2.
- Tutto async, type hints, costanti UPPER_CASE, niente segreti hardcoded.

## Output atteso

Core client + MCP server completi secondo la struttura sopra, `make
mcp-stdio-opencoesione` elenca i 5 tool, `make lint && make test` verdi. Al termine,
resoconto della discovery (cosa divergeva dalla spec) per aggiornare
`docs/specs/01-opencoesione-mcp.md`, e una nota su come il Pezzo 2 dovrà agganciare
la fonte all'orchestratore (`OPENCOESIONE_INSTRUCTIONS` + branch parser, contratto
`<!--RESOURCES_JSON-->`, R5).
