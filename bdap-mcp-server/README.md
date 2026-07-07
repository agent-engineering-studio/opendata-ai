# BDAP/SIOPE MCP server — il bilancio di un comune italiano, a portata di agente

Quanto incassa e quanto spende un comune, e su quali voci di bilancio? Questo
server MCP risponde in una chiamata, interrogando **BDAP** (Banca Dati delle
Amministrazioni Pubbliche, Ragioneria Generale dello Stato) senza scaricare
alcun file bulk.

BDAP pubblica i dati SIOPE (Sistema Informativo sulle Operazioni degli Enti
Pubblici) come dataset regionali — un file per regione/anno/tipo — ma espone
anche una risorsa **OData interrogabile riga per riga** per ciascun dataset:
questo server la usa per filtrare direttamente sul comune richiesto, senza
scaricare il dataset regionale completo (fino a 70+ MB). Fa parte del progetto
**opendata-ai** ed è il gemello degli altri server MCP del repo: wrapper
sottile sul client async condiviso in `opendata_core/bdap/`.

## Cosa fa

- Risolve la regione del comune dal suo codice ISTAT (provincia → regione),
  cerca il dataset SIOPE "Movimenti cumulati mensili" della regione/anno
  giusti nel catalogo BDAP, e interroga la sua risorsa OData filtrando su
  `codice_istat_provincia` + `codice_istat_comune` — **query mirata, non
  download bulk**.
- Restituisce entrate e spese **cumulate per titolo di bilancio** (le macro-
  categorie: entrate tributarie, trasferimenti, spese correnti, spese in
  conto capitale, ecc.), al mese più recente disponibile nell'anno.
- **Fallback automatico sugli anni precedenti** (fino a 3) se il comune non ha
  righe per l'anno richiesto — dataset non ancora pubblicato o ente non
  SIOPE-aderente in quell'anno.
- Copertura verificata: **Puglia dal 2014 al 2026** (dato corrente, aggiornato
  mensilmente) — non lo storico fermo al 2015 della vecchia serie "Gestione
  finanziaria Enti Locali", scartata perché superata.
- Ogni risultato porta un `source_url` risolvibile e un blocco `sources` con
  la licenza **CC BY** — citazione deterministica per l'orchestratore.

> Nota di scope: i dati SIOPE sono **movimenti di cassa cumulati**, non un
> bilancio contabile per competenza — utili per capire la dinamica di incassi/
> pagamenti nel tempo, non un rendiconto ufficiale certificato. Il catalogo
> BDAP non espone un'API di ricerca affidabile su query composte (verificato:
> termini multipli/frasi restituiscono 0 risultati anche quando pertinenti):
> la risoluzione regione/anno/tipo passa da un indice costruito internamente
> sul catalogo completo, non da una ricerca libera esposta come tool.

## Strumenti MCP

| Tool | Cosa fa | Argomenti chiave |
|---|---|---|
| `bdap_bilancio_comune` | Bilancio SIOPE (entrate/spese cumulate per titolo) di un comune italiano, anno più recente disponibile. | `cod_comune` — codice ISTAT del comune (es. `"072021"` per Gioia del Colle); `anno` — anno di bilancio (opzionale, default anno corrente con fallback) |

**Cosa torna** (`bdap_bilancio_comune`), un singolo oggetto JSON:

- `comune`, `denominazione`, `anno`, `popolazione` — contesto dell'ente.
- `entrate` / `spese` — lista di voci per titolo, ognuna con `codice_titolo`,
  `descrizione`, `importo_cumulato` (€, al mese più recente), `mese_riferimento`.
- `totale_entrate` / `totale_spese` — somma delle voci.
- `trovato` — `false` se nessun dato è disponibile per gli anni recenti (o il
  codice comune/provincia non è valido/mappato): mai punteggi o cifre finte.
- `source_url` — pagina tematica BDAP "Bilanci degli Enti della PA".
- `sources` — `[{ url, estratto_il, licenza }]` con la licenza CC BY.

## Avvio rapido

```bash
pip install -e ".[dev]"          # con opendata_core installato a fianco
```

**stdio** (default — per host MCP locali come Claude Desktop):

```bash
bdap-mcp-server
```

**streamable-HTTP** (per il deploy in Docker; endpoint MCP su `/mcp`):

```bash
TRANSPORT=streamable-http PORT=8080 MCP_PATH=/mcp bdap-mcp-server
# health check: GET http://localhost:8080/healthz
```

Variabili d'ambiente rilevanti:

| Variabile | Default | Note |
|---|---|---|
| `TRANSPORT` | `stdio` | `stdio` \| `streamable-http` \| `sse` |
| `HOST` | `0.0.0.0` | bind del server HTTP |
| `PORT` | `8080` | porta interna |
| `MCP_PATH` | `/mcp` | path dell'endpoint streamable-HTTP |
| `LOG_LEVEL` | `INFO` | livello di log (su stderr) |
| `BDAP_BASE_URL` | `https://bdap-opendata.rgs.mef.gov.it` | base del portale BDAP |
| `BDAP_HTTP_TIMEOUT` | `30` | timeout HTTP in secondi |
| `BDAP_CACHE_TTL_SECONDS` | `86400` | TTL cache dell'indice dataset + risultati (24h) |

## Usalo con un client MCP

### Claude Desktop (stdio)

In `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bdap-bilanci": {
      "command": "bdap-mcp-server"
    }
  }
}
```

Riavvia Claude Desktop: il tool `bdap_bilancio_comune` comparirà tra gli
strumenti disponibili.

### Altri client

Qualsiasi host MCP funziona. Per i client che parlano **streamable-HTTP**
(incluso il backend opendata-ai) avvia il server con
`TRANSPORT=streamable-http` e puntali all'endpoint `/mcp` (es.
`http://bdap-mcp:8080/mcp` dentro docker-compose, `http://localhost:18084/mcp`
in debug host-side — porta soggetta a conflitto con `socrata-mcp-server`,
verificare `SOCRATA_MCP_PORT`/`BDAP_MCP_PORT` nel compose).

## Esempio

Chiamata del tool per **Gioia del Colle** (codice ISTAT `072021`), anno 2024:

```json
{ "tool": "bdap_bilancio_comune", "arguments": { "cod_comune": "072021", "anno": 2024 } }
```

Risposta (dato reale, verificato live):

```json
{
  "comune": "072021",
  "denominazione": "COMUNE DI GIOIA DEL COLLE",
  "anno": 2024,
  "popolazione": 26502.0,
  "entrate": [
    { "codice_titolo": "E1000000000", "descrizione": "Entrate correnti di natura tributaria, contributiva e perequativa", "importo_cumulato": 5312244.28, "mese_riferimento": "2024/12" },
    { "codice_titolo": "E4000000000", "descrizione": "Entrate in conto capitale", "importo_cumulato": 3410147.99, "mese_riferimento": "2024/12" }
  ],
  "totale_entrate": 12524810.17,
  "spese": [
    { "codice_titolo": "U7000000000", "descrizione": "Uscite per conto terzi e partite di giro", "importo_cumulato": 2205474.12, "mese_riferimento": "2024/11" }
  ],
  "totale_spese": 2323044.93,
  "source_url": "https://bdap-opendata.rgs.mef.gov.it/tema/151_bilanci-degli-enti-della-pubblica-amministrazione",
  "sources": [{ "url": "...", "estratto_il": "2026-07-07", "licenza": "BDAP (Ragioneria Generale dello Stato) — Creative Commons Attribution" }],
  "trovato": true
}
```

**Come leggerla:** ogni voce è il **cumulato da inizio anno** al mese indicato
in `mese_riferimento` (SIOPE riporta movimenti di cassa progressivi, non
importi mensili isolati) — se mesi diversi hanno `mese_riferimento` diversi tra
loro, significa che per quella voce il comune non ha ancora riportato dati più
recenti del mese indicato.

## Licenza & note

- **Codice**: MIT.
- **Dati**: BDAP (RGS), licenza **Creative Commons Attribution**. Ogni
  risultato include il blocco `sources` con l'attribuzione: **cita sempre
  BDAP** negli output a valle.
- Per usi decisionali, verifica sempre sul portale ufficiale
  ([bdap-opendata.rgs.mef.gov.it](https://bdap-opendata.rgs.mef.gov.it)):
  questo server è una comodità di accesso, non la fonte autoritativa.
