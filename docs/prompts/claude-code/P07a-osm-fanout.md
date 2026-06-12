# Prompt Claude Code — P07a: OSM come specialista del fan-out

> Eseguire dalla root di `opendata-ai`, dopo i Pezzi 1–6. Leggi `CLAUDE.md` (R5) e
> `docs/specs/07-arricchimento-osm-ispra.md` §7A. Lavori in `opendata-backend/`.
> **Riusa esattamente le meccaniche del Pezzo 2** (aggancio OpenCoesione).

---

I tool OSM esistono già (`osm-mcp`: geocoding/POI/routing) ma non sono nel fan-out:
oggi OSM serve solo a rendere mappe via `attach_maps`. Promuovilo a **specialista**
che contribuisce l'**accessibilità** della zona (distanze da casello/stazione/porto,
POI vicini) alla SWOT.

Studia `factory.py` (blocco CKAN/opencoesione), `config.py` (`*_INSTRUCTIONS`,
`Settings`, `osm_mcp_url` già presente), `orchestrator/synth.py`
(`_normalise_source_tag`, `_SYNTH_SOURCE_ORDER`, gestione `preview_html` OSM),
`orchestrator/parsing.py`, `osm_map.py`/`attach_maps`.

Modifiche (tutte insieme — R5):
1. `parsing.py`: `SourceTag` includa `"osm"`.
2. `config.py`: `OSM_INSTRUCTIONS` (geocoda comune/zona, calcola distanze con routing,
   cerca POI rilevanti; emette risorse/citazioni `source:"osm"` nel blocco
   `<!--RESOURCES_JSON-->`); `Settings`: `enable_osm: bool`, `osm_agent_name="osm"`
   (riusa `osm_mcp_url`); aggiorna `SYNTH_INSTRUCTIONS` per la sezione `=== OSM ===`.
   Se il task porta la zona risolta dal Pezzo 6 (nome + centroide + bbox), l'agente
   parte dal centroide invece di rigecodare.
3. `factory.py`: importa `OSM_INSTRUCTIONS`; aggiungi `("osm", s.enable_osm)` a
   `enabled`; blocco partecipante OSM (come CKAN, fuori da `sdmx_specs`) con
   `MCPStreamableHTTPTool` su `s.osm_mcp_url`.
4. `synth.py`: `_normalise_source_tag` += `"osm"`; `_SYNTH_SOURCE_ORDER` += `"osm"`.
   Verifica che la cattura di `preview_html`/GeoJSON OSM resti coerente.
5. `geo_filter.py`: assicurati che le risorse OSM (geo) non vengano scartate.
6. `.env.local.example`/`.env.production.example`: `ENABLE_OSM`, `OSM_AGENT_NAME`.
7. Test (`tests/test_synth_merge.py`, `tests/test_config.py`): partecipante `osm`
   finto → tag corretto, sezione synth presente.

Vincoli: non duplicare la logica mappe (resta in `attach_maps`); R12 `make lint &&
make test`. Output: modifiche coerenti, test verdi, smoke di una query "zona
industriale a <comune>" che include accessibilità OSM. Riepiloga per la spec.
