# opencoesione-mcp-server

**Quanto è stato finanziato, quanto è stato davvero speso, su quali territori e
su quali temi?** Questo server MCP rende l'evidenza finanziaria della politica
di coesione italiana interrogabile da un agente AI — non un catalogo di file, ma
numeri su soldi pubblici.

Espone **OpenCoesione** (<https://opencoesione.gov.it>, i progetti finanziati
dalle politiche di coesione UE e nazionali) come strumenti per agenti LLM. È un
wrapper sottile **FastMCP** sopra l'API REST ufficiale di OpenCoesione, gemello
di `ckan-mcp-server` e `istat-mcp-server`, e fa parte della piattaforma
**opendata-ai**: una superficie unica per interrogare gli open data italiani ed
europei. La logica HTTP vive nel client async condiviso in
`opendata_core/opencoesione/`.

## Cosa fa

Risponde a domande di **trasparenza sulla spesa pubblica di coesione**:

- Quanti e quali progetti sono stati finanziati in un comune, provincia o
  regione, filtrabili per tema, natura, stato e ciclo di programmazione.
- Quanto è stato **programmato vs effettivamente pagato** su un territorio
  (totali, scomposizioni per stato/tema/natura/anno, con la popolazione di
  contesto).
- La **capacità di spesa storica** di un territorio (rapporto pagamenti / costo
  pubblico, progetti conclusi / totali): un segnale onesto sulla concreta
  capacità di portare a termine i finanziamenti.
- I **soggetti** coinvolti (programmatori, attuatori, beneficiari, realizzatori).
- Il dettaglio finanziario completo di un singolo progetto a partire dal suo CLP.

Ogni risultato è **read-only e idempotente**, e porta sempre un `source_url`
(l'URL API risolvibile di quella esatta risposta) e un blocco `sources` con data
di estrazione e licenza: la citazione è deterministica, pronta per essere
riportata a valle.

Per le domande **aggregate** che l'API paginata non può servire (scansioni
sull'intero dataset, confronti tra comuni, generatori di idee), esiste un tool
opzionale che lavora su un **mirror locale del dataset bulk** in sola lettura,
attivo solo quando è configurato `OPENCOESIONE_DB_URL`.

## Strumenti MCP

### Tool API live (sempre disponibili)

| Tool | Cosa fa | Argomenti chiave |
|---|---|---|
| `opencoesione_resolve_territorio` | Risolve un nome di luogo o un codice ISTAT nel record territorio di OpenCoesione (slug + tipo + codici). **Da chiamare per primo** quando si ha solo un nome. | `nome`, `cod_comune`, `cod_provincia`, `cod_regione`, `tipo` (C/P/R) |
| `opencoesione_search_projects` | Cerca i progetti finanziati, filtrabili per territorio e tema; record snelli (CLP, titolo, tema, stato, finanziamento, pagamenti) con `total` / `has_more` / `next_offset`. | `cod_comune`, `cod_provincia`, `cod_regione`, `territorio`, `tema`, `natura`, `stato`, `ciclo`, `limit` (max 50), `offset` |
| `opencoesione_get_project` | Dettaglio completo di un progetto dal suo CLP: scomposizione finanziaria (UE/stato/regione, impegni, pagamenti), classificazione CUP, date e fase di attuazione. | `clp` (codice locale progetto, case-insensitive) |
| `opencoesione_territorial_aggregates` | Totali di territorio: costo pubblico / pagamenti / conteggi progetti, scomposti per stato, tema, natura e anno, con la popolazione di contesto. | `cod_comune`, `cod_provincia`, `cod_regione`, `territorio`, `ciclo` |
| `opencoesione_funding_capacity` | **Tool di workflow**: `spend_ratio` (pagamenti/costo pubblico) e `conclusi_ratio` (progetti conclusi/totali) → capacità di spesa storica del territorio. Una sola chiamata. | `cod_comune`, `tema`, `ciclo`, `territorio` |
| `opencoesione_search_soggetti` | Cerca i soggetti coinvolti nei progetti per territorio/ruolo/tema/natura (l'API non supporta ricerca testuale sul nome). | `cod_comune`, `cod_provincia`, `cod_regione`, `territorio`, `ruolo`, `tema`, `natura`, `limit`, `offset` |
| `opencoesione_reference_values` | Elenca i valori di filtro validi scoperti sull'API live (temi, nature, stati, cicli) + licenza. Utile quando una chiamata filtrata sbaglia uno slug. | _(nessuno)_ |

Valori dei filtri: **temi** (ricerca-e-innovazione, reti-servizi-digitali,
competitivita-imprese, energia, ambiente, cultura-e-turismo, trasporti,
occupazione, inclusione-sociale, istruzione, capacita-amministrativa),
**stati** (non_determinabile, non_avviato, in_corso, liquidato, concluso),
**cicli** (2000_2006, 2007_2013, 2014_2020, 2021_2027), **ruoli** soggetti
(programmatore, attuatore, beneficiario, realizzatore). I codici ISTAT vengono
risolti internamente negli slug di OpenCoesione.

### Tool sul mirror locale (solo se `OPENCOESIONE_DB_URL` è impostato)

| Tool | Cosa fa | Argomenti chiave |
|---|---|---|
| `opencoesione_query_local` | Query aggregate pesanti sull'intero dataset bulk (read-only). Nessun SQL libero: si seleziona uno dei sette `kind` predefiniti. Restituisce `rows` + `dataset` (info di ingestione) + fonte/licenza bulk. | `kind`, `cod_comune`, `cod_comuni`, `cod_provincia`, `cod_regione`, `tema`, `ciclo`, `limit`, `min_peers`, `soglia_ratio` |

I sette `kind` di `opencoesione_query_local`:

| `kind` | Cosa restituisce |
|---|---|
| `spend_by_tema` | finanziamento/pagamenti per tema di un comune |
| `capacity` | spend ratio + progetti conclusi/totali di un comune (sull'intero dataset) |
| `top_soggetti` | soggetti attuatori più ricorrenti in un territorio |
| `compare_comuni` | totali affiancati per più comuni (`cod_comuni`) |
| `similar_projects` | progetti finanziati da comuni **comparabili** (stessa regione, popolazione 0,5×–2×) → generatore "fatto altrove" |
| `gap_by_tema` | temi su cui ≥`min_peers` comuni comparabili hanno finanziato progetti e questo comune ha **zero** → generatore "gap" |
| `stalled_projects` | progetti locali non conclusi con spend ratio sotto `soglia_ratio` → generatore "incompiute" |

> Usa i tool API live per il dettaglio puntuale (singolo progetto, ricerca
> fresca) e `opencoesione_query_local` per le domande aggregate, che la paginazione
> dell'API non può servire.

## Avvio rapido

```bash
pip install -e ".[dev]"          # con opendata_core installato a fianco
```

**stdio** (default — per host MCP locali come Claude Desktop):

```bash
opencoesione-mcp-server
```

**streamable-HTTP** (per il deploy Docker; endpoint su `/mcp`, porta interna 8082):

```bash
TRANSPORT=streamable-http PORT=8082 opencoesione-mcp-server
# → http://0.0.0.0:8082/mcp   (health check su /healthz)
```

Variabili d'ambiente:

| Variabile | Default | Note |
|---|---|---|
| `TRANSPORT` | `stdio` | `stdio` \| `streamable-http` \| `sse` |
| `HOST` | `0.0.0.0` | bind host (transport HTTP) |
| `PORT` | `8080` | porta interna del servizio (8082 nella topologia opendata-ai) |
| `MCP_PATH` | `/mcp` | path dell'endpoint streamable-HTTP |
| `LOG_LEVEL` | `INFO` | livello di log |
| `OPENCOESIONE_BASE_URL` | `https://opencoesione.gov.it/it/api` | root dell'API REST |
| `OPENCOESIONE_HTTP_TIMEOUT` | `60` | timeout HTTP (secondi) |
| `OPENCOESIONE_CACHE_TTL_SECONDS` | `3600` | TTL cache risposte API |
| `OPENCOESIONE_DB_URL` | _(non impostata)_ | DSN del mirror bulk locale (read-only); abilita `opencoesione_query_local` |

> Nota: l'API risponde con HTTP 429 dopo poche richieste ravvicinate; il client
> rispetta l'attesa suggerita (cap 15s, max 4 tentativi) e mette in cache le
> risposte (TTL 1h di default).

## Usalo con un client MCP

Configurazione per **Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "opencoesione": {
      "command": "opencoesione-mcp-server",
      "env": {
        "TRANSPORT": "stdio"
      }
    }
  }
}
```

Per abilitare anche le query aggregate sul mirror locale, aggiungi
`"OPENCOESIONE_DB_URL": "postgresql://…"` nel blocco `env`.

Qualsiasi altro client MCP funziona allo stesso modo: lancialo via **stdio**
(come sopra) oppure, per un deploy condiviso, in **streamable-HTTP** puntando il
client a `http://<host>:8082/mcp`.

## Esempio

Quanto è stato finanziato a Gioia del Colle (ISTAT comune `072021`) e su cosa?

1. **`opencoesione_resolve_territorio`** `{ "nome": "Gioia del Colle", "tipo": "C" }`
   → slug del territorio + codici ISTAT (utile se non hai già il codice).
2. **`opencoesione_funding_capacity`** `{ "cod_comune": "072021" }`
   → `spend_ratio` e `conclusi_ratio`: quanto del finanziamento è stato davvero
   speso e quanti progetti sono stati conclusi.
3. **`opencoesione_search_projects`** `{ "cod_comune": "072021", "tema": "trasporti", "limit": 20 }`
   → l'elenco dei progetti finanziati sul tema, ciascuno con CLP, importo e
   pagamenti; poi `opencoesione_get_project` su un CLP per il dettaglio completo.

Ogni risposta porta `source_url` + `sources` pronti da citare.

## Licenza & note

Codice: **MIT**.

Dati: i risultati dell'**API OpenCoesione** sono rilasciati con licenza
**CC BY-SA 3.0**; i **dataset bulk** (usati dal mirror locale via
`OPENCOESIONE_DB_URL`) con licenza **CC BY 4.0**. Ogni output dei tool include
l'URL di origine e la licenza nel blocco `sources`: **mantieni l'attribuzione**
e cita la fonte (OpenCoesione, <https://opencoesione.gov.it>) negli output a
valle.
