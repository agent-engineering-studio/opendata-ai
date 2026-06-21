# web-mcp 🔎🌐

**La ricerca sul web come tool MCP** — porta il "cosa fanno gli altri enti" dentro l'agente, senza incollare link a mano e senza API key proprietarie.

Wrapper FastMCP che espone due strumenti — **ricerca web** e **fetch di una pagina** — appoggiati a un'istanza **[SearXNG](https://docs.searxng.org/) self-hosted** (meta-search privacy-friendly, gratuita, senza chiavi di terze parti). Serve la sorgente **marketing-territoriale** di **opendata-ai**: trovare iniziative e best practice di altri comuni/regioni da citare come precedente, poi aprirne la pagina per leggerla e riportarla. Transport: **stdio** (host MCP locali tipo Claude Desktop) o **streamable-HTTP** su `/mcp` (porta interna `8080`, per Docker/produzione).

## Cosa fa

- **Cerca sul web** iniziative, notizie e best practice di altre pubbliche amministrazioni (un comune simile che ha lanciato un progetto turismo / mobilità / sicurezza), restituendo risultati snelli pronti per l'LLM.
- **Scarica la pagina** di un risultato promettente (testo troncato + URL finale dopo i redirect) così l'agente può leggerla e citarla con la fonte giusta.
- **Backend SearXNG self-hosted**: nessuna API key Google/Bing/Tavily, le query restano sulla tua infrastruttura. Il provider è astratto in `opendata_core.web`, così domani un'API hosted (Tavily/Brave) si innesta senza toccare questo server.
- **Una sola immagine, due transport**: stdio per il debug locale e gli host MCP desktop, streamable-HTTP per il fan-out backend in Docker.

## Strumenti MCP

| Tool | Cosa fa | Argomenti chiave |
|---|---|---|
| `web_search` | Cerca sul web iniziative, notizie e best practice di altri enti. Restituisce `{query, results: [{title, url, snippet, date, engine}]}`. Conviene orientare la query verso fonti istituzionali con operatori (`site:gov.it`, `intitle:`, `"..."`). | `query` (str, full-text con operatori), `max_results` (int, default `8`, cap a `15`) |
| `web_fetch` | Scarica una pagina e ne restituisce il testo troncato, così l'agente può citarla. L'URL restituito è quello finale dopo i redirect — è quello da citare. Risponde `{url, content, truncated, size_bytes, content_type}` o `{url, content: null, error}` in caso di errore. | `url` (str, tipicamente un `result.url` di `web_search`) |

Entrambi sono **fail-safe**: in caso di errore di rete/provider tornano un payload con `error` invece di sollevare eccezioni, così l'orchestratore non si blocca.

## Avvio rapido

```bash
cd web-mcp && pip install -e ".[dev]"

# stdio (default — host MCP locali, debug)
TRANSPORT=stdio \
SEARXNG_BASE_URL=http://localhost:8080 \
web-mcp-server

# streamable-HTTP (Docker / produzione) — espone /mcp sulla porta 8080
TRANSPORT=streamable-http \
HOST=0.0.0.0 PORT=8080 MCP_PATH=/mcp \
SEARXNG_BASE_URL=http://searxng:8080 \
web-mcp-server
```

Healthcheck HTTP: `GET /healthz` → `{"status": "ok"}`.

### Variabili d'ambiente

| Env | Default | Note |
|---|---|---|
| `TRANSPORT` | `stdio` | `stdio` \| `streamable-http` \| `sse` |
| `HOST` / `PORT` / `MCP_PATH` | `0.0.0.0` / `8080` / `/mcp` | wiring streamable-HTTP |
| `WEB_SEARCH_PROVIDER` | `searxng` | unico provider implementato (hook Tavily/Brave previsti) |
| `SEARXNG_BASE_URL` | `http://localhost:8080` | `http://searxng:8080` dentro compose |
| `WEB_SEARCH_MAX_RESULTS` | `8` | default risultati, cap a 15 |
| `WEB_MAX_FETCH_BYTES` | `524288` (512 KB) | soglia di troncamento di `web_fetch` |
| `WEB_HTTP_TIMEOUT` | `30` | timeout HTTP (secondi) |
| `LOG_LEVEL` | `INFO` | livello di log |

> ⚠️ SearXNG deve avere il formato `json` abilitato (`search.formats: [html, json]` nel suo
> `settings.yml`): la config di default serve solo HTML. Senza, `web_search` torna un errore
> esplicito che lo segnala.

## Usalo con un client MCP

Esempio per **Claude Desktop** (`claude_desktop_config.json`), transport stdio:

```json
{
  "mcpServers": {
    "web": {
      "command": "web-mcp-server",
      "env": {
        "TRANSPORT": "stdio",
        "SEARXNG_BASE_URL": "http://localhost:8080"
      }
    }
  }
}
```

Qualunque altro host MCP (Cursor, Cline, l'orchestratore di opendata-ai, ...) funziona allo stesso modo: stdio puntando all'eseguibile `web-mcp-server`, oppure streamable-HTTP verso `http://<host>:8080/mcp`.

## Esempio

```text
# 1) trova un precedente da un altro ente
web_search(query='comune borgo cammino turismo lento site:gov.it', max_results=5)
→ {
    "query": "comune borgo cammino turismo lento site:gov.it",
    "results": [
      {
        "title": "Cammini e turismo lento — Comune di ...",
        "url": "https://www.comune.esempio.gov.it/cammini",
        "snippet": "Il progetto per la valorizzazione dei cammini ...",
        "date": "2025-09-12",
        "engine": "google"
      },
      ...
    ]
  }

# 2) apri la pagina per leggerla e citarla
web_fetch(url='https://www.comune.esempio.gov.it/cammini')
→ {
    "url": "https://www.comune.esempio.gov.it/cammini",
    "content": "Cammini e turismo lento ... (testo troncato) ...",
    "truncated": true,
    "size_bytes": 524288,
    "content_type": "text/html"
  }
```

## Licenza & note

Licenza **MIT** (vedi `pyproject.toml`). Fa parte del monorepo **opendata-ai** — il build context delle immagini è la **root del repo** (copia `opendata_core/` accanto ai sorgenti del servizio); vedi il `Dockerfile` e `docker-publish.yml`. La logica di ricerca/fetch vive in `opendata_core.web`: questo server cabla solo il transport e registra i due tool.
