# ISPRA IdroGEO MCP server — il rischio idrogeologico dei comuni italiani, a portata di agente

Quanta parte di un comune è soggetta a frane o alluvioni? Quante persone vivono
in aree a pericolosità elevata? Questo server MCP risponde in una chiamata,
trasformando la **piattaforma ISPRA IdroGEO** in uno strumento che un agente AI
può interrogare direttamente.

I vincoli ambientali — pericolosità da frana e da alluvione — sono dati pubblici
ma sepolti in un'API specialistica. Questo wrapper FastMCP li espone come un tool
MCP semplice e leggibile dall'LLM: passi un codice ISTAT di comune e ottieni le
percentuali di superficie e la popolazione esposta per ogni classe di
pericolosità, con la citazione della fonte già pronta. Fa parte del progetto
**opendata-ai** ed è il gemello degli altri server MCP del repo (CKAN, ISTAT/SDMX,
OSM): wrapper sottile sul client async condiviso in `opendata_core/ispra/`.

## Cosa fa

- Interroga l'API IdroGEO di ISPRA (`https://idrogeo.isprambiente.it/api`) a
  **livello di comune ISTAT**, in una sola richiesta HTTP.
- Restituisce, per ciascuna classe di pericolosità, la **quota di superficie
  comunale** e la **popolazione esposta**:
  - **frane** (IFFI/PAI): classi P4 (molto elevata), P3 (elevata), P2, P1, AA
    (aree di attenzione) + l'**aggregato P3+P4**, il numero chiave per i vincoli
    di espansione edilizia;
  - **idraulica/alluvioni** (D.Lgs. 49/2010): P3 (elevata), P2 (media), P1 (bassa).
- Aggiunge sempre il contesto del comune: nome, superficie in km² e popolazione
  residente (censimento 2021, fallback 2011).
- Ogni risultato è **read-only e idempotente**, porta un `source_url`
  risolvibile e un blocco `sources` con la licenza **CC BY-SA 3.0 IT** —
  citazione deterministica per l'orchestratore.
- Il dato è stabile: il client lo **cache per 24h** (riduce il carico su ISPRA).

> Nota di scope: il **consumo di suolo** ISPRA non espone alcuna API REST
> utilizzabile (solo tabelle comunali XLSX annuali e servizi cartografici) e
> quindi **non** è esposto qui.

## Strumenti MCP

| Tool | Cosa fa | Argomenti chiave |
|---|---|---|
| `ispra_risk_indicators` | Indicatori di pericolosità **frane + alluvioni** per un comune italiano da IdroGEO. Per ogni classe restituisce la **quota di superficie comunale** e la **popolazione esposta**. | `cod_comune` — codice ISTAT del comune (es. `"072006"` per Bari), accettato sia zero-padded sia come intero |

**Cosa torna** (`ispra_risk_indicators`), un singolo oggetto JSON:

- `cod_comune`, `nome`, `area_kmq`, `popolazione_residente` — contesto del comune.
- `frane` — lista di classi (P4, P3, P2, P1, AA), ognuna con:
  - `classe`, `area_kmq` (superficie a quella pericolosità), `area_pct`
    (**% della superficie comunale** in quella classe), `popolazione` e
    `popolazione_pct` (popolazione esposta e sua quota).
- `frane_p3p4` — l'**aggregato "pericolosità elevata o molto elevata"** (P3+P4),
  stessa struttura: è il dato sintetico più usato per valutare i vincoli di
  espansione.
- `idraulica` — lista delle classi alluvionali P3/P2/P1, stessa struttura
  (`area_pct` = % di superficie a quella pericolosità idraulica, ecc.).
- `source_url` — URL dell'endpoint IdroGEO interrogato.
- `sources` — `[{ url, estratto_il, licenza }]` con la licenza CC BY-SA 3.0 IT.

I campi numerici sono `null` quando ISPRA non fornisce il valore per quel comune.

## Avvio rapido

```bash
pip install -e ".[dev]"          # con opendata_core installato a fianco
```

**stdio** (default — per host MCP locali come Claude Desktop):

```bash
ispra-mcp-server
```

**streamable-HTTP** (per il deploy in Docker; endpoint MCP su `/mcp`, porta interna 8083):

```bash
TRANSPORT=streamable-http PORT=8083 MCP_PATH=/mcp ispra-mcp-server
# health check: GET http://localhost:8083/healthz
```

Variabili d'ambiente rilevanti:

| Variabile | Default | Note |
|---|---|---|
| `TRANSPORT` | `stdio` | `stdio` \| `streamable-http` \| `sse` |
| `HOST` | `0.0.0.0` | bind del server HTTP |
| `PORT` | `8080` | porta interna; nel deploy opendata-ai si usa **8083** |
| `MCP_PATH` | `/mcp` | path dell'endpoint streamable-HTTP |
| `LOG_LEVEL` | `INFO` | livello di log (su stderr) |
| `ISPRA_IDROGEO_BASE_URL` | `https://idrogeo.isprambiente.it/api` | base dell'API ISPRA |
| `ISPRA_HTTP_TIMEOUT` | `30` | timeout HTTP in secondi |
| `ISPRA_CACHE_TTL_SECONDS` | `86400` | TTL cache (dato stabile → 24h) |

## Usalo con un client MCP

### Claude Desktop (stdio)

In `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ispra-idrogeo": {
      "command": "ispra-mcp-server"
    }
  }
}
```

Riavvia Claude Desktop: il tool `ispra_risk_indicators` comparirà tra gli
strumenti disponibili.

### Altri client

Qualsiasi host MCP funziona. Per i client che parlano **streamable-HTTP**
(incluso il backend opendata-ai) avvia il server con
`TRANSPORT=streamable-http` e puntali all'endpoint `/mcp` (es.
`http://ispra-mcp:8083/mcp` dentro docker-compose, `http://localhost:8083/mcp`
in debug host-side).

## Esempio

Chiamata del tool per **Gioia del Colle** (codice ISTAT `072021`):

```json
{ "tool": "ispra_risk_indicators", "arguments": { "cod_comune": "072021" } }
```

Risposta (estratto illustrativo):

```json
{
  "cod_comune": "072021",
  "nome": "Gioia del Colle",
  "area_kmq": 206.5,
  "popolazione_residente": 27123,
  "frane_p3p4": { "classe": "p3p4", "area_pct": 1.8, "popolazione": 410, "popolazione_pct": 1.5 },
  "idraulica": [
    { "classe": "p3", "area_pct": 0.4, "popolazione": 120, "popolazione_pct": 0.4 },
    { "classe": "p2", "area_pct": 1.1, "popolazione": 350, "popolazione_pct": 1.3 },
    { "classe": "p1", "area_pct": 2.6, "popolazione": 700, "popolazione_pct": 2.6 }
  ],
  "source_url": "https://idrogeo.isprambiente.it/api/pir/comuni/72021",
  "sources": [{ "url": "...", "estratto_il": "2026-06-20", "licenza": "ISPRA IdroGEO — CC BY-SA 3.0 IT" }]
}
```

**Come leggerla:** `frane_p3p4.area_pct = 1.8` significa che l'1,8% della
superficie comunale ricade in pericolosità da frana elevata o molto elevata, e
circa 410 residenti vi sono esposti. Per l'idraulica, ~2,6% della superficie è
in classe P1 (bassa).

Importante: questi valori sono **vincoli di pianificazione e indicatori di
esposizione**, non un giudizio sul comune. Servono a fondare la fattibilità
ambientale di una proposta territoriale (dove si può espandere, dove no), non a
classificare un territorio come "buono" o "cattivo".

## Licenza & note

- **Codice**: MIT.
- **Dati**: ISPRA IdroGEO, licenza **CC BY-SA 3.0 IT**. Ogni risultato include
  il blocco `sources` con l'attribuzione: **cita sempre ISPRA** negli output a
  valle (e ridistribuisci eventuali rielaborazioni con la stessa licenza).
- I dati di pericolosità vanno **verificati** sulla piattaforma ufficiale
  ([idrogeo.isprambiente.it](https://idrogeo.isprambiente.it)) per usi
  decisionali: questo server è una comodità di accesso, non la fonte autoritativa.
