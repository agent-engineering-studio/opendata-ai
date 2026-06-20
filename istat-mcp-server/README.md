# istat-mcp-server

**Una sola interfaccia SDMX per le statistiche ufficiali di ISTAT, Eurostat e OECD — esposta a qualsiasi LLM via MCP.**

`istat-mcp-server` (alias *istat-mcp*) è un wrapper [FastMCP](https://modelcontextprotocol.io)
sulle API REST **SDMX 2.1**. Nato per ISTAT, parla lo stesso dialetto SDMX di
Eurostat e OECD: la **stessa identica immagine** interroga tutte e tre le fonti
cambiando solo gli argomenti `agency` / `base_url`. Fa parte del progetto
**opendata-ai**, dove alimenta — insieme a `ckan-mcp-server` e `osm-mcp` — il
fan-out multi-fonte dell'orchestratore del backend. Niente FastAPI, niente codice
LLM: solo strumenti puliti che un modello può chiamare in autonomia.

## Cosa fa

- Espone la pipeline canonica SDMX come strumenti MCP: **scopri** i dataflow,
  **ispeziona** la struttura (DSD, codelist, vincoli), **risolvi** i codici e
  infine **scarica** le osservazioni come CSV.
- Una sola immagine, tre fonti: ISTAT (`IT1`), Eurostat (`ESTAT`), OECD (`all`)
  via `agency` + `base_url` per chiamata.
- Catalogo dataflow in cache in memoria: dopo la prima `list_dataflows`, le query
  successive con keyword diverse sono servite dalla cache.
- Protezioni anti-contesto integrate: i payload di metadati troppo grandi (es. la
  codelist `CL_ITTER107` con tutti i comuni italiani) e i CSV oltre soglia vengono
  troncati con un *hint* su come restringere la richiesta, così il prompt LLM
  resta nei limiti del contesto.
- Una scorciatoia deterministica per la lente Commercio: `istat_imprese_comune`
  restituisce unità locali e addetti di un comune per sezione ATECO con **una sola
  chiamata** al dataflow ASIA pinnato, senza discovery a keyword.
- Due trasporti: `stdio` (per host MCP locali come Claude Desktop) e
  `streamable-http` (per il deploy in Docker, su `/mcp`).

## Strumenti MCP

| Tool | Cosa fa | Argomenti chiave |
|------|---------|------------------|
| `istat_list_dataflows` | Elenca i dataflow (dataset) di un'agenzia SDMX, con filtro opzionale per keyword. Punto di partenza della discovery. | `query`, `limit`, `agency` (default `IT1`), `base_url` |
| `istat_get_dataflow` | Metadati completi di un singolo dataflow, con tutti i riferimenti risolti (`references=all`). | `agency`, `flow_id`, `version`, `base_url` |
| `istat_get_structure` | Data Structure Definition: dimensioni, attributi e codelist referenziate (`references=children`). | `agency`, `structure_id`, `version`, `base_url` |
| `istat_get_constraints` | Valori effettivamente disponibili per ogni dimensione di un dataflow (`availableconstraint … mode=available`). | `dataflow_id`, `base_url` |
| `istat_get_codelist` | Risolve una codelist con le etichette IT/EN (es. `CL_ITTER107`, `CL_SEXISTAT1`). | `agency`, `codelist_id`, `version`, `base_url` |
| `istat_get_concept` | Recupera un concept scheme (i concetti semantici dietro una DSD). | `agency`, `scheme_id`, `version`, `base_url` |
| `istat_get_data` | Scarica le osservazioni di un dataflow come SDMX-CSV (`labels=both`), filtrabili per dimensione e periodo. | `dataflow_id`, `key`, `start_period`, `end_period`, `last_n`, `first_n`, `detail`, `base_url` |
| `istat_territorial_codes` | Gerarchia territoriale italiana (`CL_ITTER107`): di default i livelli top (Italia + macro-regioni), o l'intera codelist. | `resolve_region`, `base_url` |
| `istat_imprese_comune` | Lente Commercio: unità locali e addetti di un comune da ISTAT ASIA (dataflow `183_285`), per sezione ATECO (sezione **G** = commercio). Una chiamata, evidenza citabile. | `cod_comune` (codice ISTAT 6 cifre), `anno`, `base_url` |
| `istat_cache_stats` | Diagnostica: stato della cache in memoria dei metadati (dimensione, TTL). | — |

> Il filtro `key` di `istat_get_data` usa la grammatica SDMX a punti
> (`dim1.dim2.dim3…`): valori vuoti = wildcard. Esempio: `key="ITH5..Y_GE65"`
> filtra regione `ITH5`, qualsiasi sesso, età ≥ 65.
>
> ⚠️ **Bug noto ISTAT**: `end_period=N` restituisce dati fino a N+1. Per ottenere
> dati fino all'anno N passare `end_period=str(N-1)`, oppure preferire `last_n`.

## Tre fonti, una immagine

Lo stesso server instrada verso provider diversi tramite `agency` + `base_url`,
passati per singola chiamata:

| Fonte | `agency` | `base_url` (default) |
|-------|----------|----------------------|
| **ISTAT** | `IT1` | `https://esploradati.istat.it/SDMXWS/rest` (da `ISTAT_SDMX_BASE_URL`) |
| **Eurostat** | `ESTAT` | `https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1` |
| **OECD** | `all` | `https://sdmx.oecd.org/public/rest` |

Quando `base_url` è omesso si usa `ISTAT_SDMX_BASE_URL`; per Eurostat e OECD basta
passare l'endpoint corrispondente. `agency="all"` su OECD elenca i dataflow di
tutte le agenzie.

## Avvio rapido

Installazione editabile (dal repo `opendata-ai`):

```bash
cd istat-mcp-server
pip install -e ".[dev]"
```

**Transport stdio** (default — per host MCP locali):

```bash
ISTAT_SDMX_BASE_URL=https://esploradati.istat.it/SDMXWS/rest \
istat-mcp-server
```

**Transport streamable-HTTP** (per Docker / deploy):

```bash
TRANSPORT=streamable-http \
HOST=0.0.0.0 \
PORT=8081 \
MCP_PATH=/mcp \
ISTAT_SDMX_BASE_URL=https://esploradati.istat.it/SDMXWS/rest \
istat-mcp-server
# → endpoint MCP su http://localhost:8081/mcp, healthcheck su /healthz
```

In Docker:

```bash
# build context = repo root (per copiare opendata_core/ accanto al servizio)
docker build -f istat-mcp-server/Dockerfile -t istat-mcp-server .
docker run --rm -p 8081:8081 \
  -e TRANSPORT=streamable-http -e PORT=8081 \
  istat-mcp-server
```

Variabili d'ambiente principali:

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `ISTAT_SDMX_BASE_URL` | `https://esploradati.istat.it/SDMXWS/rest` | Endpoint SDMX 2.1 di default (sovrascrivibile per chiamata con `base_url`). |
| `ISTAT_HTTP_TIMEOUT` | — | Timeout (secondi) delle richieste HTTP verso l'endpoint SDMX. |
| `TRANSPORT` | `stdio` | `stdio` \| `streamable-http` \| `sse`. |
| `HOST` / `PORT` | `0.0.0.0` / `8081` | Bind del trasporto HTTP (porta interna del servizio nel compose opendata-ai). |
| `MCP_PATH` | `/mcp` | Path dell'endpoint streamable-HTTP. |
| `LOG_LEVEL` | `INFO` | Livello di log (su stderr). |

## Usalo con un client MCP

Configurazione **Claude Desktop** (trasporto stdio), in
`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "istat": {
      "command": "istat-mcp-server",
      "env": {
        "ISTAT_SDMX_BASE_URL": "https://esploradati.istat.it/SDMXWS/rest",
        "TRANSPORT": "stdio"
      }
    }
  }
}
```

Per la config combinata dei tre server MCP di opendata-ai (CKAN + ISTAT + OSM)
vedi [`docs/claude-desktop.md`](../docs/claude-desktop.md). Qualsiasi altro client
MCP (Cursor, Continue, agent custom via SDK) può collegarsi via stdio con lo
stesso comando, oppure puntare al trasporto streamable-HTTP su `/mcp`.

## Esempio

Sequenza tipica per ottenere la popolazione residente over-65 di una regione
italiana, partendo da zero:

```text
1. istat_list_dataflows(query="popolazione residente")
   → trova il dataflow DCIS_POPRES1 ("Popolazione residente al 1° gennaio")

2. istat_get_structure(agency="IT1", structure_id="DCIS_POPRES1")
   → mostra le dimensioni: ITTER107 (territorio), SEXISTAT1 (sesso),
     ETA1 (classe di età), TIME_PERIOD …

3. istat_get_data(
       dataflow_id="DCIS_POPRES1",
       key="ITH5..Y_GE65",          # regione ITH5, qualsiasi sesso, età ≥ 65
       last_n=1                      # solo l'ultimo anno disponibile
   )
   → CSV con l'osservazione richiesta (labels=both)
```

Per la lente Commercio di un comune basta una sola chiamata, senza discovery:

```text
istat_imprese_comune(cod_comune="072021")   # Gioia del Colle
→ unità locali e addetti totali + dettaglio per sezione ATECO
  (sezione G = commercio) + source_url ISTAT da citare come evidenza
```

## Licenza & note

Distribuito con licenza **MIT** (vedi `pyproject.toml`). Le risposte dei metadati
arrivano come SDMX-JSON (`application/vnd.sdmx.structure+json`), i dati come
SDMX-CSV (`application/vnd.sdmx.data+csv`). Tutti i tool accettano un `base_url`
opzionale per puntare a endpoint SDMX 2.1 alternativi. Le statistiche restano dei
rispettivi enti (ISTAT, Eurostat, OECD): citare sempre la fonte e rispettarne le
condizioni d'uso.
