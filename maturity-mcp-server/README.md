# maturity-mcp-server

**Una scorecard di maturità open-data — modello ODM 2025 — esposta come tool MCP.**
Dài a Claude (o a qualsiasi host MCP) la capacità di dire, in un colpo solo, *quanto*
gli open data di un ente sono completi, aperti e riusabili — e *dove* deve migliorare.

Misura la maturità open-data di una Pubblica Amministrazione secondo il modello
**ODM 2025** (+ linee guida AgID): fa harvest dei dataset da un portale CKAN, ne valuta
la qualità (5-star, FAIR, DCAT-AP_IT, ISO 25012, HVD), aggrega tutto in **4 dimensioni**
e in un **livello di maturità**, e produce raccomandazioni azionabili. Fa parte di
**opendata-ai**: la logica deterministica vive in `opendata_core.maturity`, qui è esposta
come server MCP pronto per host esterni (es. Claude Desktop). Lo scoring è 100%
deterministico; l'LLM (Claude Haiku) interviene solo, in via opzionale, per giudicare la
*comprensibilità* delle descrizioni.

## Cosa fa

- **Harvest** dei dataset di un ente da un portale CKAN (`organization_show` +
  `package_search`), con normalizzazione (tema, formati, licenza, data di aggiornamento).
- **Valutazione qualità** del singolo dataset su cinque metriche standard: 5-star di
  Tim Berners-Lee, FAIR (Findable/Accessible/Interoperable/Reusable), conformità
  DCAT-AP_IT, qualità ISO 25012, categoria HVD (High-Value Dataset) e apertura licenza.
- **Aggregazione** in 4 dimensioni ODM + overall pesato + livello di maturità.
- **Raccomandazioni** azionabili derivate dai gap aggregati (con severità e n. di dataset
  coinvolti) — anche per un ente con 0 dataset, dove la scorecard è un punto di partenza,
  non un giudizio.
- **Benchmark** tra più enti, con ranking.
- Tutto è **fail-safe**: un ente non risolvibile non blocca il confronto, e senza chiave
  Anthropic il giudizio semantico viene semplicemente saltato (scoring invariato).

## Il modello ODM 2025

Le quattro dimensioni, ciascuna 0–100:

| Dimensione | Cosa misura |
|---|---|
| **Policy** | Apertura e governance dei dati: licenze esplicite e aperte, conformità DCAT-AP_IT. |
| **Portale** | Esposizione sul portale: condivisione con licenza aperta, formati machine-readable, classificazione tematica, copertura (numero di dataset). |
| **Qualità** | Qualità intrinseca dei dataset: punteggio composito su 5-star, FAIR e ISO 25012. |
| **Impatto** | Potenziale di riuso: dataset ad alto valore (HVD), 3+ stelle, freschezza del dato. Penalizzato dalla domanda di riuso non soddisfatta. |

L'**overall** è la media pesata delle quattro dimensioni e determina il **livello di
maturità ODM**:

- **Beginner** (0–39)
- **Follower** (40–59)
- **Fast-tracker** (60–79)
- **Trend-setter** (80–100)

Sotto una soglia minima di dataset, il livello diventa **"Dato insufficiente"**: meglio
dichiarare l'incertezza che restituire un punteggio falso.

## Strumenti MCP

La pipeline tipica è **harvest → assess_quality → score_overall**. I tool di alto livello
(`score_overall`, `score_dimension`, `compare_entities`) incapsulano l'intera catena
internamente. Ogni tool accetta un `base_url` opzionale: punta a qualsiasi portale CKAN
(default: il portale configurato).

| Tool | Cosa fa | Argomenti chiave |
|---|---|---|
| `maturity_harvest_entity` | Raccoglie i dataset di un ente da CKAN e ne restituisce un riepilogo normalizzato (id, titolo, tema, formati, licenza, data). | `entity` (nome/slug/id org CKAN), `base_url?`, `max_datasets=50` |
| `maturity_assess_quality` | Valuta la qualità di **un singolo** dataset CKAN: 5-star, FAIR, DCAT-AP_IT, ISO 25012, HVD, apertura licenza, freschezza. | `dataset` (pacchetto CKAN Action API) |
| `maturity_score_overall` | Assessment **completo** dell'ente: harvest → qualità → 4 dimensioni → livello ODM → raccomandazioni. Usa Haiku per la comprensibilità delle descrizioni, se disponibile. | `entity`, `base_url?`, `max_datasets=50`, `use_semantic=true` |
| `maturity_score_dimension` | Punteggio 0–100 di **una sola** dimensione. | `entity`, `dimension` (`policy`\|`portal`\|`quality`\|`impact`), `base_url?`, `max_datasets=50` |
| `maturity_compare_entities` | **Benchmark** tra enti: overall, livello e dimensioni per ciascuno, ordinati per overall. | `entities[]`, `base_url?`, `max_datasets=50` |

## Avvio rapido

Installazione editable (parte di opendata-ai, dipende da `opendata-core`):

```bash
cd maturity-mcp-server
pip install -e ".[dev]"
```

### stdio (default — host MCP locali tipo Claude Desktop)

```bash
TRANSPORT=stdio maturity-mcp-server
```

### streamable-HTTP (Docker / deployment)

```bash
TRANSPORT=streamable-http HOST=0.0.0.0 PORT=8087 MCP_PATH=/mcp maturity-mcp-server
# endpoint MCP:  http://localhost:8087/mcp
# health check:  http://localhost:8087/healthz
```

### Variabili d'ambiente rilevanti

| Variabile | Default | A cosa serve |
|---|---|---|
| `TRANSPORT` | `stdio` | `stdio` \| `streamable-http` \| `sse` |
| `HOST` / `PORT` | `0.0.0.0` / `8080` | bind per il transport HTTP (porta interna convenzionale `8087`) |
| `MCP_PATH` | `/mcp` | path dell'endpoint streamable-HTTP |
| `CKAN_DEFAULT_BASE_URL` | `https://www.dati.gov.it/opendata` | portale CKAN di default (sovrascrivibile per-call con `base_url`) |
| `ANTHROPIC_API_KEY` | — | abilita il giudizio semantico (comprensibilità). Senza chiave viene saltato. |
| `CLAUDE_CLASSIFY_MODEL` | `claude-haiku-4-5-20251001` | modello usato per il semantico |
| `LOG_LEVEL` | `INFO` | livello di logging |

## Usalo con un client MCP

### Claude Desktop

Aggiungi al file di configurazione (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "maturity": {
      "command": "maturity-mcp-server",
      "env": {
        "TRANSPORT": "stdio",
        "CKAN_DEFAULT_BASE_URL": "https://www.dati.gov.it/opendata",
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

Riavvia Claude Desktop: i cinque tool `maturity_*` compaiono tra gli strumenti disponibili.

### Altri client

Qualsiasi host MCP compatibile (Cursor, Continue, client custom via SDK) funziona allo
stesso modo: in locale via stdio con lo stesso comando, oppure puntando all'endpoint
streamable-HTTP `http://<host>:<porta>/mcp`.

## Esempio

Valutare un comune sul portale nazionale, passo per passo.

1. **Harvest** — cosa pubblica l'ente:

   ```
   maturity_harvest_entity(entity="comune-di-gioia-del-colle")
   → { "org_title": "...", "total_on_portal": 12, "datasets": [ … ] }
   ```

2. **Qualità di un dataset** — la metrica fine sul singolo pacchetto:

   ```
   maturity_assess_quality(dataset=<pacchetto CKAN>)
   → { "stars_5": 3, "fair": {"mean": 0.62}, "dcat_ap_it": 0.8, "license_open": true, "hvd_category": null }
   ```

3. **Score complessivo** — la scorecard dell'ente:

   ```
   maturity_score_overall(entity="comune-di-gioia-del-colle")
   → {
       "n_datasets": 12,
       "scores": { "policy": 71.0, "portal": 58.0, "quality": 64.0, "impact": 40.0,
                   "overall": 59.4, "level": "Follower" },
       "recommendations": [ {"code": "...", "severity": "media", "dimension": "impact", "message": "…"} ]
     }
   ```

**Come si legge.** Overall 59.4 → livello **Follower**: l'ente pubblica con buona governance
(Policy alta), ma l'**Impatto** basso (40) segnala pochi dataset ad alto valore / poco
freschi — ed è esattamente lì che le raccomandazioni indicano dove intervenire. Per
confrontare più comuni in un colpo solo:

```
maturity_compare_entities(entities=["comune-a", "comune-b", "comune-c"])
→ { "ranking": [ … ordinati per overall … ], "errors": [ … enti non risolvibili … ] }
```

## 📣 Per i social

> 🇮🇹 Quanto sono *davvero* aperti e riusabili gli open data del tuo Comune?
>
> Abbiamo messo **una scorecard di maturità open-data ODM 2025 dentro un tool MCP**: fa
> harvest dei dataset da CKAN, li valuta su 5-star, FAIR, DCAT-AP_IT, ISO 25012 e HVD, e
> restituisce 4 dimensioni + livello (Beginner → Trend-setter) + raccomandazioni azionabili.
>
> Lo colleghi a Claude Desktop e chiedi, in linguaggio naturale: *"valuta la maturità open
> data di questo ente"*. Scoring 100% deterministico, fail-safe, multi-portale. Parte di
> **opendata-ai**. 🚀
>
> \#opendata #ODM #maturity #MCP #PA #AI #dataquality #DCAT

## Licenza & note

- Licenza **MIT** (vedi `pyproject.toml`).
- La logica di scoring è deterministica e vive in `opendata_core.maturity`; questo
  pacchetto è il wrapper FastMCP che la espone come tool.
- L'unico uso dell'LLM è il giudizio semantico opzionale (comprensibilità delle
  descrizioni) via Claude Haiku: senza `ANTHROPIC_API_KEY` viene saltato e lo scoring
  resta identico, così i test non chiamano mai la rete.
- I punteggi dipendono da ciò che l'ente effettivamente pubblica sul portale CKAN: dati
  pubblici possono essere disallineati o incompleti, e sotto la soglia minima di dataset
  il livello è onestamente **"Dato insufficiente"** anziché un punteggio falso.
