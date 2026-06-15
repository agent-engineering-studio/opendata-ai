# Spec 02 — Aggancio OpenCoesione all'orchestratore (fan-out MAF)

**Pezzo 2.** Promuove OpenCoesione (Pezzo 1) a **specialista di prima classe** nel
fan-out `ConcurrentBuilder` del backend, accanto a ckan / istat / eurostat / oecd.
Rispetta la regola **R5** del `CLAUDE.md` (il contratto `<!--RESOURCES_JSON-->` è
duplicato in più punti: toccarne uno solo rompe il contratto).

## Natura della fonte (importante)

OpenCoesione **non** è una fonte di dataset/file scaricabili (come CKAN) né SDMX
(come istat/eurostat/oecd). È una fonte **finanziaria e di fattibilità**: i suoi tool
ritornano JSON strutturato (progetti, aggregati, capacità di spesa). Di conseguenza:

- Il suo **contributo narrativo** al synth è l'evidenza di finanziamento sul
  territorio + l'indicatore di capacità attuativa storica (spend ratio).
- Le sue **risorse** (`Resource`) sono **citazioni** verso URL risolvibili dell'API
  OpenCoesione (la query `progetti.json`, il dettaglio progetto, l'aggregato),
  formato `JSON`, non file da scaricare e dare in pasto a tabelle/mappe.

Va agganciata come **specialista autonomo** (sul modello del blocco CKAN in
`factory.py`), **non** dentro il loop `sdmx_specs`.

## Contratto Pezzo 1 → Pezzo 2 (da onorare nell'MCP)

Perché `synth._capture_tool_resources` possa catturare deterministicamente le
citazioni anche se l'LLM le omette dal blocco, **ogni risultato JSON dei tool
OpenCoesione include un campo `source_url`** (l'URL API risolvibile di quella
risposta) ed eventualmente `source_label`. È l'equivalente di ciò che `csv`/`path`
sono per istat e `url`/`content` per ckan. Se il Pezzo 1 non lo espone ancora,
aggiungerlo è parte di questo pezzo.

## Punti di modifica (le "fonti di verità" da aggiornare insieme)

### 1. `orchestrator/parsing.py`
Estendere il tipo sorgente:
```python
SourceTag = Literal["ckan", "istat", "eurostat", "oecd", "opencoesione"]
```

### 2. `config.py`
- Nuovo `OPENCOESIONE_INSTRUCTIONS` — **ricalcare `CKAN_INSTRUCTIONS`** come template
  (stesso contratto: narrativa + blocco `<!--RESOURCES_JSON-->` con array di risorse;
  campi `name/url/format/source`). Deve istruire l'agente a: partire da
  `opencoesione_search_projects` sul comune ISTAT, usare
  `opencoesione_funding_capacity` per la fattibilità, ed emettere come risorse le
  citazioni `JSON` verso l'API (con `source: "opencoesione"`).
- `Settings`: aggiungere `enable_opencoesione: bool`, `opencoesione_mcp_url: str`,
  `opencoesione_agent_name: str` (default es. `"opencoesione"`), sul modello dei
  campi `ckan_*` / `istat_*`.
- Aggiornare `SYNTH_INSTRUCTIONS` perché il synth sappia che esiste una sezione
  `=== OPENCOESIONE ===` con evidenze di finanziamento/fattibilità da integrare nella
  narrativa unificata (senza inventare numeri non presenti).

### 3. `factory.py`
- Aggiungere `("opencoesione", s.enable_opencoesione)` alla lista `enabled` in
  `__aenter__`.
- Aggiungere un **blocco partecipante dedicato** (come quello CKAN, prima/dopo, fuori
  dal loop `sdmx_specs`):
  ```python
  if s.enable_opencoesione:
      oc_mcp = await self._enter_mcp_tool(
          s.opencoesione_agent_name, s.opencoesione_mcp_url,
          "Tools to query OpenCoesione (Italian cohesion-policy funded projects).",
      )
      oc_agent = await self._enter_agent(
          chat_client, OPENCOESIONE_INSTRUCTIONS, s.opencoesione_agent_name,
          [oc_mcp], default_options,
      )
      participants.append(oc_agent)
  ```
- Importare `OPENCOESIONE_INSTRUCTIONS` dal `config`.

### 4. `orchestrator/synth.py`
- `_normalise_source_tag`: aggiungere `"opencoesione"` alla tupla dei tag
  riconosciuti (è una stringa distinta, nessun conflitto di substring).
- `_SYNTH_SOURCE_ORDER`: aggiungere `"opencoesione"`.
- `_capture_tool_resources`: aggiungere un **branch `source == "opencoesione"`** che,
  dai payload dei tool, estrae `source_url` (+ `source_label`) e costruisce
  `Resource(name=..., url=source_url, format="JSON", source="opencoesione")`. Niente
  download di contenuto (sono citazioni API, non file).

### 5. `orchestrator/geo_filter.py`
- Verificare `filter_resources`: le risorse OpenCoesione sono già scoped al comune
  (l'URL porta il codice ISTAT). Assicurarsi che il filtro geografico **non le scarti
  erroneamente** quando l'utente nomina un comune. Se il filtro lavora su nomi/percorsi,
  prevedere il riconoscimento del codice ISTAT nelle URL OpenCoesione o esentare
  `source == "opencoesione"`.

### 6. `.env.local.example` / `.env.production.example`
- `ENABLE_OPENCOESIONE`, `OPENCOESIONE_MCP_URL`
  (`http://opencoesione-mcp:8080/mcp` interno / `http://localhost:<port>/mcp` host),
  `OPENCOESIONE_AGENT_NAME` (R9).

### 7. Test (R5 impone di aggiornarli insieme)
- `tests/test_config.py`: i nuovi campi `Settings` e il nuovo blocco INSTRUCTIONS.
- `tests/test_synth_merge.py`: un partecipante `opencoesione` finto che emette
  narrativa + blocco risorse + `source_url` nei tool result → verificare tag,
  ordine sezione synth, e cattura deterministica della citazione.

## Esiti implementazione (2026-06-12)

- Aggiunto il tool `opencoesione_resolve_territorio` all'MCP server (previsto
  dalla clausola "se il Pezzo 1 non lo espone ancora"): l'agente parte dal nome
  del luogo, non deve conoscere i codici ISTAT. La cattura citazioni **salta**
  i risultati di resolve (shape `{"found": ...}`) — sono infrastruttura, non
  evidenza.
- Default `enable_opencoesione=false` (come eurostat/oecd: +1 chiamata LLM per
  query, opt-in). `opencoesione_mcp_url` default host-side `:8084` perché
  `:8082` è la convenzione host-debug di eurostat; nel compose la porta interna
  resta 8082 (URL passata esplicitamente).
- Vincolo preesistente scoperto: `ConcurrentBuilder` del framework richiede
  **≥2 partecipanti** — una config con una sola fonte abilitata fallisce su
  `run()` ma funziona su `run_streaming()` (fan-out proprio, è il percorso UI).
- Smoke superato con **Ollama qwen2.5:32k locale** (oltre che coi test mockati):
  query "zona industriale di Barletta" → narrativa con spend ratio 0.38,
  82% conclusi, progetti reali citati, 2 risorse `opencoesione` nel blocco JSON.

## Fuori scope (pezzi successivi)

L'output "programma elettorale / SWOT zona industriale" è una **sintesi di livello
superiore** rispetto al synth generico (che fonde narrative). Sarà un endpoint
dedicato con struttura SWOT + proposte-ancorate-a-finanziamenti + guardrail etici
(no contenuto persuasivo, citazione obbligatoria): **Pezzo 4**. Qui ci fermiamo a
rendere OpenCoesione una fonte di prima classe nel fan-out esistente.

## Definition of Done

- [ ] `SourceTag` esteso; `make lint && make test` verdi.
- [ ] `OPENCOESIONE_INSTRUCTIONS` + campi `Settings` + `SYNTH_INSTRUCTIONS` aggiornati.
- [ ] Blocco partecipante in `factory.py` (fuori da `sdmx_specs`).
- [ ] `synth.py`: tag, ordine sezione, branch di cattura `opencoesione`.
- [ ] `geo_filter` verificato sulle risorse OpenCoesione.
- [ ] env example aggiornati con le 3 variabili.
- [ ] `test_config.py` + `test_synth_merge.py` estesi e verdi.
- [ ] Smoke: query "zona industriale a <comune pugliese>" con
      `ENABLE_OPENCOESIONE=true` → la narrativa unificata cita progetti reali e
      l'indicatore di fattibilità, con risorse `opencoesione` nel blocco JSON.
