# CKAN MCP Server

> Un solo server MCP, qualsiasi catalogo open data del mondo basato su CKAN.

`ckan-mcp-server` è un wrapper [FastMCP](https://github.com/modelcontextprotocol/python-sdk) che espone i tool dell'[Action API di CKAN](https://docs.ckan.org/en/latest/api/index.html) a qualunque client MCP (Claude Desktop, Cursor, VS Code, agenti). La parte interessante: **ogni tool accetta un argomento `base_url` per-chiamata**, quindi una sola immagine Docker interroga `dati.gov.it`, `data.gov.uk`, `data.gov`, `open.canada.ca` o qualsiasi altro portale CKAN — senza redeploy. Quando `base_url` è omesso, il server usa il default `https://www.dati.gov.it/opendata`. È uno dei componenti dell'orchestratore **opendata-ai** per open data civici italiani ed europei.

## Cosa fa

CKAN è il software dietro la maggior parte dei portali open data pubblici. Questo server traduce le sue azioni HTTP in tool MCP tipizzati e pronti per un LLM: cercare dataset, leggere i metadati completi (risorse, tag, organizzazione), navigare organizzazioni e gruppi tematici, interrogare tabelle DataStore (anche via SQL read-only) e scaricare il contenuto di risorse testuali. Le risposte dei dataset vengono "snellite" (campi essenziali, note troncate) per restare entro il contesto del modello. Tutto passa dalle API pubbliche di sola lettura: nessuna scrittura, nessuna credenziale richiesta.

## Strumenti MCP

| Tool | Cosa fa | Argomenti chiave |
|------|---------|------------------|
| `ckan_status_show` | Verifica che il portale sia raggiungibile e restituisce i metadati del sito (versione, estensioni, titolo). | `base_url` |
| `ckan_site_read` | Conferma l'accesso pubblico in lettura e restituisce il flag di autorizzazione del portale. | `base_url` |
| `ckan_package_search` | Cerca dataset con query Solr; ritorna conteggio, faccette e lista di risultati (snelliti). | `q`, `fq`, `rows` (max 10), `start`, `sort`, `base_url` |
| `ckan_package_show` | Recupera i metadati completi di un dataset (risorse, tag, organizzazione, extras). | `id`, `base_url` |
| `ckan_organization_list` | Elenca le organizzazioni del portale. | `all_fields`, `limit`, `base_url` |
| `ckan_organization_show` | Metadati di un'organizzazione, opzionalmente con i suoi dataset. | `id`, `include_datasets`, `base_url` |
| `ckan_group_list` | Elenca i gruppi (categorie tematiche) del portale. | `all_fields`, `limit`, `base_url` |
| `ckan_group_show` | Metadati di un gruppo, opzionalmente con i dataset associati. | `id`, `include_datasets`, `base_url` |
| `ckan_tag_list` | Elenca o cerca i tag del portale. | `query`, `all_fields`, `base_url` |
| `ckan_datastore_search` | Interroga le righe di una risorsa tabellare DataStore. | `resource_id`, `q`, `limit`, `offset`, `filters`, `base_url` |
| `ckan_datastore_search_sql` | Esegue una query SQL read-only sul DataStore (il nome tabella è l'UUID della risorsa). | `sql`, `base_url` |
| `ckan_resource_download` | Scarica il contenuto di una risorsa e lo restituisce come testo. Solo formati CSV, JSON, GeoJSON, TXT; per gli altri (PDF, XLSX, SHP…) restituisce solo l'URL. | `resource_url`, `format` |

Ogni tool accetta l'argomento opzionale `base_url` (URL radice del portale, es. `https://data.gov.uk`): è questo che rende una sola istanza utilizzabile contro qualsiasi catalogo CKAN.

## Avvio rapido

### stdio (host MCP locali)

```bash
pip install -e .
TRANSPORT=stdio ckan-mcp-server
```

### Streamable HTTP (Docker / container)

```bash
docker build -t ckan-mcp-server .          # build context = repo root
docker run --rm -p 8080:8080 \
  -e TRANSPORT=streamable-http \
  -e CKAN_DEFAULT_BASE_URL=https://www.dati.gov.it/opendata \
  ckan-mcp-server
```

Endpoint MCP: `http://localhost:8080/mcp` (porta interna `8080`). Healthcheck su `GET /healthz`.

### Variabili d'ambiente

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `TRANSPORT` | `stdio` | `stdio` \| `streamable-http` \| `sse` |
| `HOST` | `0.0.0.0` | Indirizzo di bind per i transport HTTP |
| `PORT` | `8080` | Porta per i transport HTTP |
| `MCP_PATH` | `/mcp` | Mount path dello Streamable HTTP |
| `CKAN_DEFAULT_BASE_URL` | `https://www.dati.gov.it/opendata` | Portale di default quando `base_url` è omesso |
| `CKAN_HTTP_TIMEOUT` | `30` | Timeout per richiesta, in secondi |
| `LOG_LEVEL` | `INFO` | Livello di logging Python |

## Usalo con un client MCP

### Claude Desktop (stdio)

In `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ckan": {
      "command": "ckan-mcp-server",
      "env": { "CKAN_DEFAULT_BASE_URL": "https://www.dati.gov.it/opendata" }
    }
  }
}
```

### Cursor, VS Code e altri client MCP

Qualsiasi client MCP funziona. Per i client stdio usa lo stesso `command`/`env` dell'esempio sopra; per i client che parlano HTTP avvia il server con `TRANSPORT=streamable-http` e puntalo all'endpoint `http://localhost:8080/mcp`.

## Esempio

Chiamata al tool `ckan_package_search` su un portale diverso dal default:

```json
{
  "tool": "ckan_package_search",
  "arguments": {
    "q": "qualità dell'aria",
    "rows": 3,
    "base_url": "https://www.dati.gov.it/opendata"
  }
}
```

Risposta (snellita per l'LLM):

```json
{
  "count": 42,
  "results": [
    {
      "name": "dati-qualita-aria-2025",
      "title": "Dati qualità dell'aria 2025",
      "organization": "arpa-esempio",
      "tags": ["aria", "ambiente", "pm10"],
      "resources": [
        { "name": "centraline.csv", "format": "CSV", "url": "https://…/centraline.csv" }
      ]
    }
  ]
}
```

Da qui un agente può chiamare `ckan_package_show` per i metadati completi, oppure `ckan_resource_download` sull'URL del CSV per leggerne il contenuto.

## Licenza & note

Il codice del server è rilasciato sotto licenza **MIT** ed è infrastruttura del progetto **opendata-ai** (vedi il [README della root](../README.md) per l'architettura completa). I dataset restituiti restano soggetti alla **licenza del portale di origine**: verifica sempre i termini d'uso del catalogo CKAN che stai interrogando prima di riusare i dati.
