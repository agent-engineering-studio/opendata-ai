# Prompt Claude Code — P10: Marketing territoriale (modulo spunti di attrattività)

> Eseguire dalla root di `opendata-ai`, dopo i Pezzi 1–9. Leggi `CLAUDE.md` (R1, R3,
> R5, R12, R13) e `docs/specs/10-marketing-territorio.md`. Tocchi `opendata_core/`,
> un nuovo package `web-mcp/`, `opendata-backend/`, il frontend `opendata-ai-ui/` e
> l'infra `agent-engineering-studio-infra/`. La fonte web è **SearXNG self-hosted**
> dietro un MCP, non i tool nativi di Claude.

---

Aggiungi al report un **secondo motore di idee** dedicato al **marketing
territoriale** (turismo, viabilità/mobilità, sicurezza/vivibilità, attrattività/
brand): nuova `modalita="marketing"` su `POST /programma` e **sezione di report
distinta** dalle Idee finanziabili (Pezzo 8), che restano intatte. Abilitato da una
9ª fonte web (`web-mcp` → SearXNG). Usa il pattern del Pezzo 2 (aggancio fonte) e
del Pezzo 9 (campo derivato non falsificabile).

## 1. Fonte web (3 livelli)

- `opendata_core/`: client async HTTP `searxng` con `web_search(query, max_results,
  region?)` e `web_fetch(url)` → `{title, url, snippet, date}`. Provider astratto
  `WEB_SEARCH_PROVIDER` (`searxng` default; lascia il gancio per `tavily`/`brave`).
  **Niente FastMCP qui.**
- `web-mcp/`: nuovo package FastMCP (pattern `ckan-mcp-server/`): `pyproject.toml`
  con `[dev]`, server che espone i 2 tool, transport stdio + streamable-http
  (`TRANSPORT`, `HOST`, `PORT`, `MCP_PATH=/mcp`), `Dockerfile` con **context = repo
  root** (R1, copia `opendata_core/` + `web-mcp/` affiancati). `make mcp-stdio-web`.

## 2. Backend — fan-out (R5: aggiorna insieme parsing + le prompt-template + synth)

1. `parsing.py`: `SourceTag` += `"web"`.
2. `config.py`:
   - `WEB_INSTRUCTIONS`: cerca **iniziative analoghe di altri enti** e best practice
     per il tema; **solo** risultati con URL risolvibile e data; emetti come risorse
     i risultati con `source:"web"`. Stesso blocco `<!--RESOURCES_JSON-->` delle
     altre fonti.
   - `MARKETING_INSTRUCTIONS` (analogo a `IDEE_INSTRUCTIONS`): 4 lenti
     (`turismo_cultura`, `viabilita_mobilita`, `sicurezza_vivibilita`,
     `attrattivita_brand`), 3 generatori (`caso_analogo`, `asset_sottoutilizzato`,
     `domanda_emergente`), regola (A)+(B) sotto, ordine priorità×fattibilità.
     `caso_analogo` esterni consentiti fuori Puglia con bias peer-group, dichiarato.
   - `Settings`: `enable_web`, `web_mcp_url`, `web_agent_name="web"`,
     `web_search_provider="searxng"`, `searxng_base_url`, `web_search_max_results=8`.
   - `SYNTH_INSTRUCTIONS`: sezione `=== WEB ===` (ispirazione esterna).
3. `factory.py`: importa le instructions; `("web", s.enable_web)` in `enabled`;
   blocco partecipante web come opencoesione (fuori da `sdmx_specs`),
   `_enter_mcp_tool(s.web_agent_name, s.web_mcp_url, "Web search over external
   initiatives and territorial best practices.")`.
4. `synth.py`: `_normalise_source_tag` += `"web"`; `_SYNTH_SOURCE_ORDER` += `"web"`
   (ultimo); branch `source=="web"` in `_capture_tool_resources` → `Resource(
   name=title, url=url, format="WEB", source="web",
   description=f"{snippet[:140]} — {date or 's.d.'}")`.

## 3. Motore marketing (Pezzo 8 → marketing)

- `ProgrammaRequest.modalita` += `"marketing"`; in `factory.py`/`synth.py` la
  modalità `marketing` fa un solo fan-out che alimenta il `marketing_agent`
  (come `completa` con le Idee).
- `guardrails.py`: `GENERATORI_MARKETING = ("caso_analogo","asset_sottoutilizzato",
  "domanda_emergente")`; `_generatore_marketing_ok(voce)`:
  - **(A)** ≥1 evidenza locale (fonte ∈ {istat,opencoesione,osm,ispra,ckan,kg});
  - **(B)** ≥1 evidenza `source:"web"` con URL risolvibile;
  - voce senza (A)&(B) → scartata; URL `web` non risolvibile → evidenza scartata;
  - `fattibilita.livello` non `"alta"` su sola base esterna (degrada a `media`).
- Contratto (`orchestrator/programma.py`): `Evidenza.fonte_tipo: Literal[
  "dato_locale","ispirazione_esterna"]` **derivato** da `model_validator`
  (`fonte=="web"` → `ispirazione_esterna`), sul modello di `Evidenza.tier`.

## 4. Frontend (ritocco Pezzo 5)

- `lib/types.ts`: `ResourceSource` += `"web"`; `Evidenza` += `fonte_tipo`;
  modalità `marketing`.
- `lib/programmaPdf.ts`: nuova sezione "Marketing territoriale — spunti di
  attrattività" (pattern card Idee), raggruppata per lente, badge fattibilità +
  badge fonte (`dato_locale`/`ispirazione_esterna`). Disclaimer rafforzato:
  disallineamento open data + ruolo ingestion KG + "spunti di posizionamento, non
  atti né progetti finanziati".
- `app/territorio/page.tsx`: toggle "Marketing".

## 5. Infra `agent-engineering-studio-infra/` (deploy Aruba)

- `docker-compose.opendata.yml`: servizio `searxng` (immagine upstream
  `searxng/searxng`, rete `opendata-internal`, niente esposizione pubblica) +
  servizio `web-mcp` (immagine GHCR, `TRANSPORT=streamable-http`, `PORT=8080`,
  `MCP_PATH=/mcp`, `SEARXNG_BASE_URL=http://searxng:8080`); aggiungi
  `WEB_MCP_URL: http://web-mcp:8080/mcp`, `ENABLE_WEB`, `WEB_SEARCH_PROVIDER`,
  `SEARXNG_BASE_URL`, `WEB_SEARCH_MAX_RESULTS` all'env del backend + `depends_on`.
- `.env.opendata.example`: `ENABLE_WEB=true`, `WEB_SEARCH_PROVIDER=searxng`,
  `WEB_SEARCH_MAX_RESULTS=8`.
- `Makefile`: aggiungi `searxng web-mcp` agli elenchi servizi di
  `down/logs-opendata`.
- Deploy: `SERVICES=(... web-mcp searxng)` nel `deploy-aruba.yml` (repo opendata-ai)
  e, se presente, in quello dell'infra.
- CI opendata-ai `docker-publish.yml`: matrix += `{ name: web-mcp, context: .,
  dockerfile: web-mcp/Dockerfile }`; trigger path += `web-mcp/**`.

## Vincoli / test

- R1 context repo root; R3 test su `/tmp/oda-venv`; R5 contratto risorse aggiornato
  ovunque; R12 `make lint && make test`; R13 il web è una **fonte** (MCP), non si
  espone marketing via A2A.
- Test: partecipante `web` finto con `web_search` mockato → tag/cattura `web`;
  voce marketing senza evidenza `web` → scartata; senza locale → scartata; URL non
  risolvibile → evidenza scartata; `fonte_tipo` derivato; fattibilità non `"alta"`
  su sola base esterna. Aggiorna `test_guardrails.py`, `test_config.py`,
  `test_synth_merge.py`.

## Output atteso

`web-mcp` + client SearXNG, fonte `web` nel fan-out, `modalita="marketing"` con i 3
generatori e il guardrail (A)+(B), sezione report + toggle UI, infra Aruba
aggiornata, test verdi. Smoke (Puglia, modalità marketing): ≥1 spunto per lente,
ognuno con premessa locale citata + precedente esterno con URL e badge "ispirazione
esterna". Riepiloga gli scostamenti di discovery per aggiornare la spec 10.
