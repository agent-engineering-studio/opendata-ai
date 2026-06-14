# Spec 10 — Marketing territoriale (modulo "spunti di attrattività")

**Pezzo 10.** Aggiunge al report "Analisi del territorio" (`POST /programma`) un
**secondo motore di idee** dedicato al **marketing territoriale** — turismo,
viabilità/mobilità dolce, sicurezza/vivibilità, attrattività/brand — che vive
*fuori* dai progetti di finanziamento. Le idee finanziabili (Pezzo 8) restano
intatte: il marketing è una **modalità e una sezione di report distinte**, così
il consiglio comunale legge un brainstorming difendibile senza confonderlo con i
progetti di coesione.

## Perché serve un motore separato

Tre vincoli rendono il marketing impossibile dentro le "Idee" attuali, *by design*:

1. I 4 generatori (`gap_comparativo`, `fabbisogno`, `incompiuto`,
   `finestra_finanziamento` in `guardrails.py`) sono tutti modellati sul
   finanziamento: producono idee solo nella forma "spesa da accelerare / fondo da
   intercettare".
2. Il guardrail `FactChecker` impone l'ancoraggio a OpenCoesione/ISTAT/ISPRA: una
   voce turistica "senza progetto" viene scartata, non è che non venga generata.
3. Non esiste una fonte di "notizie / iniziative altrui" da cui prendere spunto.

Il marketing territoriale è una scelta di posizionamento/animazione/comunicazione
che spesso si ispira a casi analoghi altrove. Va quindi aggiunto come modulo
parallelo, con generatori, guardrail, fonte e sezione propri.

## La fonte abilitante: `web-mcp` sopra SearXNG (gratis, provider-agnostico)

L'unico pezzo nuovo di ingegneria è una fonte "web/news". Tre livelli, pattern
identico a CKAN/OSM:

- **SearXNG** — meta-motore open-source **self-hosted** (immagine upstream
  `searxng/searxng`, nessun codice). Aggrega Google/Bing/DuckDuckGo, espone una
  JSON API (`/search?format=json`). **Costo €0**, nessuna API key di terzi.
- **`opendata_core/`** — client async HTTP verso SearXNG (`web_search`,
  `web_fetch`). Solo logica, **niente FastMCP** (invariante CLAUDE.md). Provider
  astratto via `WEB_SEARCH_PROVIDER` (`searxng` default; `tavily`/`brave`
  opzionali domani, cambiando solo il client).
- **`web-mcp/`** — wrapper FastMCP che espone i 2 tool, transport stdio +
  streamable-http su `/mcp` (pattern `ckan-mcp-server/`, build context = repo
  root, R1). Entra nel fan-out come 9ª fonte.

Perché un MCP e non una chiamata diretta: nel repo i tool arrivano all'LLM **solo**
via `MCPStreamableHTTPTool` (`factory.py`). Per far "cercare sul web" all'agente
marketing dentro il fan-out, la capacità deve essere un tool MCP.

**Scartate (14/06/2026):** tool nativi Anthropic `web_search`/`web_fetch`
(fatturati per-ricerca, attivi solo con provider `claude` — in dev/prod si gira
anche su Ollama — e il wrapper `agent_framework_anthropic` non li espone, passa
solo MCP); Bing grounding via Azure Foundry (solo Azure, a pagamento, non cablato).

## Wiring nel fan-out (pattern Pezzo 2 / Pezzo 9)

1. `orchestrator/parsing.py`: `SourceTag` += `"web"`.
2. `config.py`:
   - `WEB_INSTRUCTIONS`: data l'analisi (comune + tema), cerca **iniziative
     analoghe di altri enti** e best practice; riporta solo risultati con URL
     risolvibile e data; emetti come risorse i risultati con `source:"web"`.
     Stesso contratto `<!--RESOURCES_JSON-->` delle altre fonti (**R5**: è la 5ª
     prompt-template che lo emette — aggiornare anche il parser).
   - `MARKETING_INSTRUCTIONS`: istruzioni dell'`marketing_agent` (analogo a
     `IDEE_INSTRUCTIONS`) con le 4 lenti e lo schema JSON delle voci.
   - `Settings`: `enable_web`, `web_mcp_url`, `web_agent_name="web"`,
     `web_search_provider="searxng"`, `web_search_max_results=8`,
     `searxng_base_url`; aggiorna `SYNTH_INSTRUCTIONS` per la sezione `=== WEB ===`.
3. `factory.py`: `("web", s.enable_web)` in `enabled`; blocco partecipante web
   (come opencoesione, fuori da `sdmx_specs`), `_enter_mcp_tool(s.web_agent_name,
   s.web_mcp_url, "Web search over external initiatives and territorial best practices.")`.
4. `synth.py`: `_normalise_source_tag` += `"web"`; `_SYNTH_SOURCE_ORDER` += `"web"`
   (ultimo); branch `source=="web"` in `_capture_tool_resources` → per ogni
   risultato `Resource(name=title, url=url, format="WEB", source="web",
   description=f"{snippet[:140]} — {date or 's.d.'}")`.

## Il motore marketing (evoluzione Pezzo 8)

- `ProgrammaRequest.modalita`: `Literal["scheda","idee","completa","marketing"]`.
  Come `completa`, **un solo fan-out** alimenta il `marketing_agent` in parallelo.
- **Lenti tematiche (asse "cosa")**, v1 tutte e 4:
  `turismo_cultura`, `viabilita_mobilita`, `sicurezza_vivibilita`, `attrattivita_brand`.
- **Generatori (asse "come nasce l'idea")** in `guardrails.py`:
  `GENERATORI_MARKETING = ("caso_analogo", "asset_sottoutilizzato", "domanda_emergente")`.

| Generatore | Logica | Ancoraggio richiesto |
|---|---|---|
| `caso_analogo` | "Un ente simile ha lanciato l'iniziativa X di successo → adattabile qui" | ≥1 **precedente esterno** (`source:"web"`, URL fetchabile) **+** premessa di applicabilità locale (peer group) |
| `asset_sottoutilizzato` | "Asset locale verificabile poco valorizzato in chiave attrattiva" | ≥1 **asset reale** (`osm`/`ckan`/`opencoesione`) **+** spunto esterno di valorizzazione (`web`) |
| `domanda_emergente` | "Un trend/domanda che i dati mostrano, a cui rispondere con animazione/servizi" | ≥1 **indicatore locale** (`istat`/`osm`) **+** caso esterno (`web`) |

## Guardrail (A)+(B) — restare difendibili (no propaganda)

`_generatore_marketing_ok()` in `guardrails.py`. Ogni voce marketing **deve** citare
due cose distinte ed etichettate:

- **(A) premessa locale verificabile** da una delle 8 fonti esistenti (un asset,
  un flusso, un dato demografico, un vincolo);
- **(B) precedente esterno fetchabile**: ≥1 evidenza `source:"web"` con URL
  risolvibile e data, presentata come *spunto/ispirazione*, mai come prova.

Contratto: ogni `Evidenza` acquisisce `fonte_tipo: Literal["dato_locale",
"ispirazione_esterna"]`, **derivato e non falsificabile** via `model_validator`
(`fonte=="web"` → `ispirazione_esterna`, altrimenti `dato_locale`) — stesso pattern
di `Evidenza.tier` (Pezzo 9). Una voce senza almeno una (A) **e** una (B) è scartata.
`fattibilita.livello` non può essere `"alta"` su sola base esterna.

**PUGLIA (produzione):** i `caso_analogo` esterni restano **consentiti fuori
regione** (sono spunti, non interventi locali), ma con bias di pertinenza su
peer-group/area vasta dichiarato nelle `MARKETING_INSTRUCTIONS` — **non**
geo-bloccati come zone/`/programma` (`TERRITORIO_PROVINCE` non si applica al web).

## Report + UI (tocco al Pezzo 5)

- **Nuova sezione PDF** "Marketing territoriale — spunti di attrattività"
  (`opendata-ai-ui/lib/programmaPdf.ts`, pattern card delle Idee), raggruppata per
  lente, con badge fattibilità + **badge fonte** (`dato_locale` vs
  `ispirazione_esterna`). NON mescolata con "Idee per il territorio".
- `app/territorio/page.tsx`: toggle "Marketing" (`modalita="marketing"`), export
  markdown/PDF; `lib/types.ts`: `ResourceSource` += `"web"`, `Evidenza` += `fonte_tipo`.
- **Disclaimer rafforzato** (vale per tutte le modalità, vedi nota memoria
  *disclaimer-opendata-disallineamento*): oltre a "non costituisce materiale
  elettorale", aggiungere (1) gli open data possono essere **disallineati** dallo
  stato reale dell'amministrazione per ritardi burocratici; (2) l'ingestion KG
  aggiorna la conoscenza e **sollecita l'allineamento** dei dati. In modalità
  marketing aggiungere: "spunti di posizionamento, non atti amministrativi né
  progetti finanziati".

## Prerequisito operativo (non codice)

SearXNG va deployato come servizio (vedi infra `aes-infra`). Configurare i motori
abilitati e il `format: json` nelle `settings.yml` di SearXNG; rispettare i ToS dei
motori a monte e un rate-limit prudente. Preferire fonti istituzionali
(`*.gov.it`, stampa, siti comuni, agenzie regionali turismo) via bias di query.

## Definition of Done

- [ ] `opendata_core/`: client SearXNG async (`web_search`, `web_fetch`),
      provider astratto `WEB_SEARCH_PROVIDER`.
- [ ] `web-mcp/`: wrapper FastMCP (2 tool), stdio + streamable-http `/mcp`,
      Dockerfile (context repo root, R1), `pyproject` con `[dev]`.
- [ ] `SourceTag` += web; `WEB_INSTRUCTIONS` + `MARKETING_INSTRUCTIONS`; Settings
      (`enable_web`, `web_mcp_url`, `web_search_provider`, `searxng_base_url`,
      `web_search_max_results`); blocco partecipante in `factory.py`.
- [ ] `synth.py`: tag/ordine/cattura `web` (`Resource` `WEB` con snippet+data).
- [ ] `parsing.py` + le 4+1 prompt-template aggiornate insieme (**R5**).
- [ ] `modalita="marketing"`; `GENERATORI_MARKETING` + `_generatore_marketing_ok`;
      `Evidenza.fonte_tipo` derivato; guardrail (A)+(B); fattibilità conservativa
      su sola base esterna.
- [ ] Frontend: sezione "Marketing territoriale" nel PDF + toggle UI;
      `ResourceSource` += web; badge fonte; disclaimer rafforzato.
- [ ] Infra `aes-infra`: servizi `searxng` + `web-mcp` nell'overlay, env,
      Makefile, deploy; CI `docker-publish` matrix += `web-mcp`.
- [ ] Test (`/tmp/oda-venv`, R3): partecipante `web` finto con `web_search`
      mockato → tag/cattura corretti; voce marketing senza (B) → scartata; URL non
      risolvibile → scartato; `fonte_tipo` derivato; fattibilità non `"alta"` su
      sola base esterna; `test_guardrails.py`, `test_config.py`, `test_synth_merge.py`.
- [ ] `make lint && make test` verdi (R12).
- [ ] Smoke: comune Puglia in modalità marketing → la sezione mostra ≥1 spunto per
      lente, ognuno con una premessa locale citata + un precedente esterno con URL
      e badge "ispirazione esterna".

## Fuori scope

- Qualità/ranking dei risultati SearXNG oltre il bias di pertinenza (responsabilità
  della config SearXNG).
- Generazione di contenuti di marketing veri e propri (testi campagna, creatività):
  qui si producono **spunti** difendibili, non materiale promozionale.
