"""Chat-client factory + OrchestratorSession that wires three agents.

Three agents are constructed on session entry:
  - ckan  : `Agent` with MCPStreamableHTTPTool against the CKAN MCP server
            + CKAN_INSTRUCTIONS
  - istat : `Agent` with MCPStreamableHTTPTool against the ISTAT MCP server
            + ISTAT_INSTRUCTIONS
  - synth : tool-less `Agent` with SYNTH_INSTRUCTIONS

The CKAN+ISTAT pair is wrapped in a ConcurrentBuilder workflow with the synth
agent's `.run()` used inside the aggregator callback (see workflow.py / synth.py).

`build_chat_client` is a copy of ckan_agent.factory.build_chat_client (kept in
sync by convention; duplication is intentional under the side-by-side layout).
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable

import httpx

if TYPE_CHECKING:
    from .byok import BYOKCreds
from agent_framework import Agent, MCPStreamableHTTPTool
from opendata_core.osm.client import OverpassError
from opendata_core.sdmx.client import SdmxError

from .cache.store import cache_get, cache_set

from .config import (
    CKAN_INSTRUCTIONS,
    EUROSTAT_INSTRUCTIONS,
    IDEE_INSTRUCTIONS,
    ISPRA_INSTRUCTIONS,
    ISTAT_INSTRUCTIONS,
    KG_INSTRUCTIONS,
    MARKETING_INSTRUCTIONS,
    ODS_INSTRUCTIONS,
    OECD_INSTRUCTIONS,
    OPENCOESIONE_INSTRUCTIONS,
    OSM_INSTRUCTIONS,
    PROGRAMMA_INSTRUCTIONS,
    SYNTH_INSTRUCTIONS,
    WEB_INSTRUCTIONS,
    Settings,
    resolve_provider,
)
from .orchestrator.programma import (
    ProgrammaRequest,
    ProgrammaResponse,
    build_programma_aggregator,
    build_programma_task,
)
from .orchestrator.parsing import parse_agent_reply
from .orchestrator.synth import _normalise_source_tag, build_aggregator
from .orchestrator.workflow import build_workflow

log = logging.getLogger("orchestrator.factory")

# Dataset-search source set: CKAN + the SDMX family (ISTAT/Eurostat/OECD). Used to
# scope the fan-out for "find me the data" entry points (the /esplora route AND
# the A2A search/geo skills) so they don't drag in OpenCoesione/ISPRA/OSM/web —
# those belong to the /territorio profile. Single source of truth, passed as
# `sources=` to run_streaming. eurostat/oecd are opt-in; harmless if disabled.
DATASET_SOURCES = frozenset({"ckan", "ods", "istat", "eurostat", "oecd"})

# Upstream sources for the best-effort lenses (Overpass, Nominatim, ISTAT SDMX) are
# routinely unreachable, throttled or slow — that is an expected operating
# condition, not a bug. We log those at WARNING as a single line (the lens is just
# skipped) and reserve full tracebacks for genuinely unexpected errors so real
# bugs still stand out. OverpassError/SdmxError both subclass RuntimeError.
_EXPECTED_LENS_ERRORS: tuple[type[BaseException], ...] = (
    TimeoutError,
    OSError,
    httpx.HTTPError,
    OverpassError,
    SdmxError,
)


def _osm_object_url(hit: dict[str, Any], clat: float, clon: float) -> str:
    """URL OSM dell'oggetto geocodificato (es. la relation del comune, che mostra dati
    e tag reali) invece di una vista mappa generica `#map=` senza contenuto. Fallback
    alla mappa centrata solo se Nominatim non ha restituito osm_type/osm_id."""
    otype, oid = hit.get("osm_type"), hit.get("osm_id")
    if otype and oid:
        return f"https://www.openstreetmap.org/{otype}/{oid}"
    return f"https://www.openstreetmap.org/#map=13/{clat:.5f}/{clon:.5f}"


def _log_lens_skip(msg: str, *args: object, exc: BaseException) -> None:
    """Log a skipped best-effort lens, suppressing the traceback for expected outages."""
    if isinstance(exc, _EXPECTED_LENS_ERRORS):
        log.warning(f"{msg} (%s: %s)", *args, type(exc).__name__, exc)
    else:
        log.warning(msg, *args, exc_info=exc)


# Le ancore deterministiche (zona/commercio/turismo) interrogano fonti statiche
# (confini/zone OSM, ASIA ISTAT) lente o intermittenti. Le memorizziamo su Redis
# 24h così, una volta ottenute, /programma le riusa senza re-interrogare Overpass
# /SDMX (sopravvive ai restart, condivisa tra worker). Solo i risultati POSITIVI
# vengono messi in cache: un'assenza dovuta a un'outage transitoria NON deve
# oscurare la lente per 24h — si ritenta alla richiesta successiva.
_LENS_TTL = 24 * 3600

# Rete di sicurezza per le lenti OSM che NON hanno già un `wait_for` interno
# (zona, zone_commerciali): un socket appeso non deve trascinare l'intera fase
# "evidenze territoriali". Volutamente GENEROSO (= al ceiling delle lenti più
# lente già esistenti, istruzione/sanità a 90s): con Overpass che fallisce in
# fretta sui mirror morti (connect corto) questo guardrail NON scatta mai nel
# percorso sano — protegge solo dalle patologie, senza degradare una lente viva.
_LENS_SAFETY_TIMEOUT = 90.0

# Etichette-fonte delle 10 lenti territoriali: emesse come `source` negli eventi
# di streaming così la UI mostra una checklist live ("come il thinking") invece
# di un'unica barra opaca "evidenze territoriali". Stringhe già leggibili → il
# frontend le mostra senza dover mantenere un dizionario parallelo.
_LENS_SOURCES: dict[str, str] = {
    "zona": "Zona selezionata",
    "zone_comm": "Zone commerciali",
    "commercio": "Commercio · imprese ISTAT",
    "turismo": "Turismo e cultura",
    "lavoro": "Lavoro e competenze",
    "trasporti": "Trasporti e mobilità",
    "welfare": "Welfare e coesione sociale",
    "istruzione": "Istruzione · scuole",
    "ambiente": "Ambiente · rischio idrogeologico",
    "sanita": "Sanità di prossimità",
    "comparabili": "Comparabili · progetti peer (OpenCoesione)",
}


async def _lens_cached(parts: tuple[str, ...], producer):  # noqa: ANN001, ANN202
    """Cache-aside su Redis per un'ancora best-effort. `producer` è una factory
    che ritorna la coroutine da eseguire al cache-miss. Fail-open: se Redis non
    c'è, `cache_get`/`cache_set` sono no-op e si esegue sempre il producer."""
    key = "od:lens:" + ":".join(p for p in parts if p)
    cached = await cache_get(key)
    if cached is not None:
        return cached
    result = await producer()
    if result is not None:
        await cache_set(key, result, ttl_seconds=_LENS_TTL)
    return result


def build_chat_client(settings: Settings, byok: "BYOKCreds | None" = None) -> Any:
    """Return a Microsoft Agent Framework chat client.

    When `byok` is set, the client uses the USER's own credential (their Claude
    API key or Ollama Cloud key) instead of the system provider — this is how a
    BYOK user runs the service without a subscription. Otherwise the configured
    system provider is resolved as before.
    """
    if byok is not None:
        log.info("Building BYOK chat client (provider=%s)", byok.provider)
        if byok.provider == "claude":
            from agent_framework_anthropic import AnthropicClient

            return AnthropicClient(api_key=byok.api_key, model=settings.claude_model)
        if byok.provider == "ollama_cloud":
            from agent_framework_ollama import OllamaChatClient
            from ollama import AsyncClient as OllamaAsyncClient

            cloud_client = OllamaAsyncClient(
                host=settings.ollama_cloud_base_url,
                headers={"Authorization": f"Bearer {byok.secret}"},
            )
            return OllamaChatClient(
                client=cloud_client,
                model=byok.model or settings.ollama_cloud_model,
            )
        if byok.provider == "ollama_local":
            # The user's own Ollama server: `secret` is its base URL, no auth.
            from agent_framework_ollama import OllamaChatClient

            return OllamaChatClient(
                host=byok.secret,
                model=byok.model or settings.ollama_llm_model,
            )
        raise RuntimeError(f"Unsupported BYOK provider={byok.provider!r}")

    provider = resolve_provider(settings)
    log.info("Building chat client for provider=%s (configured=%s)", provider, settings.llm_provider)

    if provider == "ollama":
        from agent_framework_ollama import OllamaChatClient

        log.info(
            "Ollama: host=%s model=%s",
            settings.ollama_base_url, settings.ollama_llm_model,
        )
        return OllamaChatClient(
            host=settings.ollama_base_url,
            model=settings.ollama_llm_model,
        )

    if provider == "ollama_cloud":
        if not settings.ollama_cloud_api_key:
            raise RuntimeError(
                "OLLAMA_CLOUD_API_KEY is required when the system provider is ollama_cloud"
            )
        from agent_framework_ollama import OllamaChatClient
        from ollama import AsyncClient as OllamaAsyncClient

        log.info("Ollama Cloud (system): host=%s model=%s",
                 settings.ollama_cloud_base_url, settings.ollama_cloud_model)
        cloud_client = OllamaAsyncClient(
            host=settings.ollama_cloud_base_url,
            headers={"Authorization": f"Bearer {settings.ollama_cloud_api_key}"},
        )
        return OllamaChatClient(
            client=cloud_client,
            model=settings.ollama_cloud_model,
        )

    if provider == "azure_foundry":
        if not settings.azure_ai_project_endpoint:
            raise RuntimeError(
                "AZURE_AI_PROJECT_ENDPOINT is required when LLM_PROVIDER=azure_foundry"
            )
        if not settings.azure_ai_model_deployment_name:
            raise RuntimeError(
                "AZURE_AI_MODEL_DEPLOYMENT_NAME is required when LLM_PROVIDER=azure_foundry"
            )
        from agent_framework_foundry import FoundryChatClient
        from azure.identity.aio import DefaultAzureCredential

        return FoundryChatClient(
            project_endpoint=settings.azure_ai_project_endpoint,
            model=settings.azure_ai_model_deployment_name,
            credential=DefaultAzureCredential(),
        )

    if provider == "claude":
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is required when LLM_PROVIDER=claude"
            )
        from agent_framework_anthropic import AnthropicClient

        return AnthropicClient(
            api_key=settings.anthropic_api_key,
            model=settings.claude_model,
        )

    raise RuntimeError(f"Unsupported LLM_PROVIDER={provider!r}")


class OrchestratorSession:
    """Async context that holds the workflow + up to four specialist agents.

    The three SDMX-based specialists (istat / eurostat / oecd) share the same
    `istat-mcp-server` instance — its tools are SDMX 2.1 generic and only
    differ by `agency` + `base_url` per call. Each agent still gets its own
    `MCPStreamableHTTPTool` instance because the framework expects per-agent
    connection lifecycles.

    Lifecycle:
        async with OrchestratorSession(settings) as session:
            merged_text = await session.run("popolazione Toscana 2023")
    """

    def __init__(self, settings: Settings, byok: "BYOKCreds | None" = None) -> None:
        self._settings = settings
        # When set, every agent in this session runs on the user's own LLM
        # credential (BYOK) instead of the system provider. A per-user session
        # is built fresh per request; the shared system session has byok=None.
        self._byok = byok
        self._stack = AsyncExitStack()
        self._participants: list[Agent] = []
        self._synth_agent: Agent | None = None
        self._programma_agent: Agent | None = None
        self._idee_agent: Agent | None = None
        self._marketing_agent: Agent | None = None
        self._enabled_sources: list[str] = []
        # agent-framework workflows reject concurrent .run() on the same instance,
        # and the participant Agents are shared — serialise requests with a lock.
        self._lock = asyncio.Lock()

    async def _enter_mcp_tool(self, name: str, url: str, description: str) -> MCPStreamableHTTPTool:
        tool = MCPStreamableHTTPTool(name=name, url=url, description=description)
        await self._stack.enter_async_context(tool)
        return tool

    async def _enter_agent(
        self,
        chat_client: Any,
        instructions: str,
        name: str,
        tools: list[Any] | None,
        default_options: dict[str, object] | None,
    ) -> Agent:
        agent = Agent(
            chat_client,
            instructions=instructions,
            name=name,
            tools=tools,
            default_options=default_options or None,
        )
        await self._stack.enter_async_context(agent)
        return agent

    async def __aenter__(self) -> "OrchestratorSession":
        s = self._settings
        enabled = [
            label for label, on in (
                ("ckan", s.enable_ckan),
                ("ods", s.enable_ods),
                ("istat", s.enable_istat),
                ("eurostat", s.enable_eurostat),
                ("oecd", s.enable_oecd),
                ("opencoesione", s.enable_opencoesione),
                ("osm", s.enable_osm),
                ("ispra", s.enable_ispra),
                ("kg", s.enable_kg),
                ("web", s.enable_web),
            )
            if on
        ]
        if not enabled:
            raise RuntimeError(
                "At least one source must be enabled "
                "(enable_ckan / ods / istat / eurostat / oecd / opencoesione / osm / ispra / kg / web)"
            )
        self._enabled_sources = enabled
        log.info(
            "OrchestratorSession starting | provider=%s sources=%s",
            s.llm_provider, ",".join(enabled),
        )

        chat_client = build_chat_client(s, self._byok)
        default_options: dict[str, object] = {}
        if self._byok is None and resolve_provider(s) == "ollama":
            default_options["num_ctx"] = s.ollama_num_ctx
            default_options["temperature"] = s.ollama_temperature

        participants: list[Agent] = []

        if s.enable_ckan:
            ckan_mcp = await self._enter_mcp_tool(
                s.ckan_agent_name,
                s.ckan_mcp_url,
                "Tools to query any CKAN open data portal via the Action API.",
            )
            ckan_agent = await self._enter_agent(
                chat_client, CKAN_INSTRUCTIONS, s.ckan_agent_name, [ckan_mcp], default_options,
            )
            participants.append(ckan_agent)

        # OpenDataSoft specialist — same shape as CKAN (one portal per call, ODSQL
        # filters). Opt-in; joins the dataset fan-out (DATASET_SOURCES) when enabled.
        if s.enable_ods:
            ods_mcp = await self._enter_mcp_tool(
                s.ods_agent_name,
                s.ods_mcp_url,
                "Tools to query any OpenDataSoft portal via the Explore API v2.1.",
            )
            ods_agent = await self._enter_agent(
                chat_client, ODS_INSTRUCTIONS, s.ods_agent_name, [ods_mcp], default_options,
            )
            participants.append(ods_agent)

        # Each SDMX specialist dials its OWN MCP server instance (same image,
        # different ISTAT_SDMX_BASE_URL) → the agent never passes a base_url.
        sdmx_specs: list[tuple[bool, str, str, str, str]] = [
            (s.enable_istat,    s.istat_agent_name,    ISTAT_INSTRUCTIONS,    s.istat_mcp_url,    "ISTAT SDMX tools (esploradati.istat.it)."),
            (s.enable_eurostat, s.eurostat_agent_name, EUROSTAT_INSTRUCTIONS, s.eurostat_mcp_url, "Eurostat SDMX tools (ec.europa.eu/eurostat)."),
            (s.enable_oecd,     s.oecd_agent_name,     OECD_INSTRUCTIONS,     s.oecd_mcp_url,     "OECD SDMX tools (sdmx.oecd.org)."),
        ]
        for on, name, instructions, url, desc in sdmx_specs:
            if not on:
                continue
            tool = await self._enter_mcp_tool(name, url, desc)
            agent = await self._enter_agent(
                chat_client, instructions, name, [tool], default_options,
            )
            participants.append(agent)

        # OpenCoesione is a standalone specialist (like CKAN, outside the SDMX
        # loop): financial/feasibility evidence, citations via `source_url`.
        if s.enable_opencoesione:
            oc_mcp = await self._enter_mcp_tool(
                s.opencoesione_agent_name,
                s.opencoesione_mcp_url,
                "Tools to query OpenCoesione (Italian cohesion-policy funded projects).",
            )
            oc_agent = await self._enter_agent(
                chat_client,
                OPENCOESIONE_INSTRUCTIONS,
                s.opencoesione_agent_name,
                [oc_mcp],
                default_options,
            )
            participants.append(oc_agent)

        # OSM specialist (accessibility). Reuses the same osm-mcp server that
        # already renders maps — here it joins the fan-out with the geocoding/
        # POI/routing/zone tools.
        if s.enable_osm:
            osm_mcp = await self._enter_mcp_tool(
                s.osm_agent_name,
                s.osm_mcp_url,
                "OpenStreetMap tools: geocoding, nearby places, routing, recognised zones.",
            )
            osm_agent = await self._enter_agent(
                chat_client, OSM_INSTRUCTIONS, s.osm_agent_name, [osm_mcp], default_options,
            )
            participants.append(osm_agent)

        # Knowledge Graph (deployment esterno): evidenza documentale da
        # delibere/piani/bilanci ingeriti. Il server kg-mcp espone anche tool
        # di scrittura (kg_ingest/kg_delete_document) — qui montiamo il suo
        # endpoint read e le KG_INSTRUCTIONS NON menzionano i tool write; la
        # protezione vera (esporre solo i read) sta nel deployment del KG.
        if s.enable_kg:
            kg_mcp = await self._enter_mcp_tool(
                s.kg_agent_name,
                s.kg_mcp_url,
                "Read-only Knowledge Graph tools over ingested PA documents.",
            )
            kg_agent = await self._enter_agent(
                chat_client, KG_INSTRUCTIONS, s.kg_agent_name, [kg_mcp], default_options,
            )
            participants.append(kg_agent)

        # ISPRA IdroGEO specialist (environmental constraints).
        if s.enable_ispra:
            ispra_mcp = await self._enter_mcp_tool(
                s.ispra_agent_name,
                s.ispra_mcp_url,
                "ISPRA IdroGEO tools: landslide/flood hazard indicators per comune.",
            )
            ispra_agent = await self._enter_agent(
                chat_client, ISPRA_INSTRUCTIONS, s.ispra_agent_name, [ispra_mcp], default_options,
            )
            participants.append(ispra_agent)

        # Web search specialist (marketing territoriale, Pezzo 10): web-mcp over
        # a self-hosted SearXNG. Surfaces EXTERNAL initiatives by other public
        # bodies to take inspiration from — the `ispirazione_esterna` half of the
        # marketing (A)+(B) guardrail.
        if s.enable_web:
            web_mcp = await self._enter_mcp_tool(
                s.web_agent_name,
                s.web_mcp_url,
                "Web search + fetch over external initiatives and territorial best practices.",
            )
            web_agent = await self._enter_agent(
                chat_client, WEB_INSTRUCTIONS, s.web_agent_name, [web_mcp], default_options,
            )
            participants.append(web_agent)

        # Optional A2A remote specialist (Phase 3 / Import). When enabled, the
        # orchestrator fans out to a remote A2A-compliant agent as a peer. It
        # appears in the same loop as CKAN / ISTAT — same lifecycle, same
        # `_worker` wrapper, same aggregator hook. Lives behind a feature flag
        # so absence-of-config is the safe default.
        if s.a2a_specialist_url:
            from .orchestrator.a2a_specialist import A2ARemoteAgent

            remote = A2ARemoteAgent(
                name=s.a2a_specialist_name,
                url=s.a2a_specialist_url,
                bearer=s.a2a_specialist_bearer,
            )
            await self._stack.enter_async_context(remote)
            participants.append(remote)  # type: ignore[arg-type]
            log.info("Added A2A remote specialist | name=%s url=%s",
                     s.a2a_specialist_name, s.a2a_specialist_url)

        if len(participants) < 1:
            raise RuntimeError("No participants enabled — refusing to start")

        # Gli agenti tool-less di sintesi (synth/programma/idee) emettono l'output
        # FINALE lungo (prosa + JSON ricco). Senza max_tokens il client Anthropic
        # taglia a 1024 token → JSON troncato → report vuoto. Alziamo il tetto.
        # temperature=0: per il JSON strutturato vogliamo determinismo, non
        # creatività di sintassi (a T~1 il modello ogni tanto droppa una virgola).
        synth_options: dict[str, object] = {
            **default_options,
            "temperature": 0.0,
            "max_tokens": s.synth_max_tokens,
        }
        # Le IDEE (e il marketing) vogliono VARIETÀ: a temperature 0 il modello
        # emette ogni volta l'intervento più ovvio per ogni lente (turismo→posti
        # letto, lavoro→NEET, commercio→DUC) → idee tutte uguali. Una temperatura
        # moderata sblocca originalità restando ancorata alle evidenze; il
        # programma (SWOT/JSON) resta a 0 per il determinismo della sintassi.
        idee_options: dict[str, object] = {
            **synth_options,
            "temperature": float(os.getenv("IDEE_TEMPERATURE", "0.5")),
        }

        synth_agent = await self._enter_agent(
            chat_client, SYNTH_INSTRUCTIONS, s.synth_agent_name, None, synth_options,
        )
        self._synth_agent = synth_agent

        # Agente tool-less della scheda programma (come il synth, istruzioni
        # diverse). Con provider claude può girare su un modello dedicato.
        if s.enable_programma:
            programma_client = chat_client
            # A dedicated programma model only applies to the SYSTEM Claude
            # provider — a BYOK user runs everything on their own credential, so
            # we never spin up a second client on the system key for them.
            if s.programma_model and self._byok is None and resolve_provider(s) == "claude":
                from agent_framework_anthropic import AnthropicClient

                programma_client = AnthropicClient(
                    api_key=s.anthropic_api_key, model=s.programma_model,
                )
            self._programma_agent = await self._enter_agent(
                programma_client, PROGRAMMA_INSTRUCTIONS, s.programma_agent_name,
                None, synth_options,
            )
            # Modalità "idee" (Pezzo 8): stesso client, istruzioni dedicate.
            self._idee_agent = await self._enter_agent(
                programma_client, IDEE_INSTRUCTIONS, f"{s.programma_agent_name}-idee",
                None, idee_options,
            )
            # Modalità "marketing" (Pezzo 10): stesso client, istruzioni dedicate.
            self._marketing_agent = await self._enter_agent(
                programma_client, MARKETING_INSTRUCTIONS, f"{s.programma_agent_name}-marketing",
                None, idee_options,
            )

        # Store the building blocks; a FRESH workflow + aggregator are built
        # per request in run() / run_streaming() because (a) agent-framework
        # workflow instances cannot be re-run concurrently (single-shot), and
        # (b) the aggregator needs the per-call user query to apply the
        # deterministic geographic filter on the final resource set.
        self._participants = participants
        log.info(
            "OrchestratorSession ready (%d participants + synth)", len(participants)
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        self._participants = []
        self._synth_agent = None
        self._programma_agent = None
        self._idee_agent = None
        self._marketing_agent = None
        await self._stack.aclose()

    @staticmethod
    async def _resolve_zona(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Ancora ZONA con cache Redis 24h (vedi `_lens_cached`)."""
        if not req.zona_osm_id:
            return None
        return await _lens_cached(
            ("zona", req.zona_osm_id),
            lambda: OrchestratorSession._resolve_zona_uncached(req),
        )

    @staticmethod
    async def _resolve_zona_uncached(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Zona OSM selezionata (Pezzo 6) → {name, centroid, bbox} per il task.

        Best-effort: se Overpass non risponde si procede senza zona risolta
        (l'analisi degrada a livello comune, come da catena di fallback).
        """
        if not req.zona_osm_id:
            return None
        try:
            from opendata_core.osm import zones as osm_zones

            osm_type, _, osm_id = req.zona_osm_id.partition("/")
            feature = await asyncio.wait_for(
                osm_zones.get_zone(osm_type, osm_id or osm_type),
                timeout=_LENS_SAFETY_TIMEOUT,
            )
            if feature is None:
                return None
            geom = feature.get("geometry") or {}
            props = feature.get("properties") or {}

            def _coords():
                t = geom.get("type")
                if t == "Point":
                    yield geom["coordinates"]
                elif t == "Polygon":
                    yield from geom.get("coordinates", [[]])[0]
                elif t == "MultiPolygon":
                    for poly in geom.get("coordinates", []):
                        yield from poly[0]

            lons = [c[0] for c in _coords()]
            lats = [c[1] for c in _coords()]
            if not lons:
                return None
            bbox = [min(lats), min(lons), max(lats), max(lons)]
            return {
                "name": props.get("name"),
                "centroid": {"lat": (bbox[0] + bbox[2]) / 2, "lon": (bbox[1] + bbox[3]) / 2},
                "bbox": bbox,
            }
        except Exception as exc:
            _log_lens_skip("zona OSM %s non risolta — procedo a livello comune",
                           req.zona_osm_id, exc=exc)
            return None

    @staticmethod
    async def _resolve_zone_commerciali(req: ProgrammaRequest) -> list[dict[str, Any]] | None:
        """Ancora ZONE COMMERCIALI con cache Redis 24h (vedi `_lens_cached`)."""
        if req.modalita not in ("idee", "completa") or not req.comune_nome:
            return None
        return await _lens_cached(
            ("zone_commerciali", req.cod_comune, req.comune_nome or ""),
            lambda: OrchestratorSession._resolve_zone_commerciali_uncached(req),
        )

    @staticmethod
    async def _resolve_zone_commerciali_uncached(
        req: ProgrammaRequest,
    ) -> list[dict[str, Any]] | None:
        """Zone candidate per localizzare il gap COMMERCIO (lente Commercio/DUC).

        Cerca le aree a vocazione commerciale (landuse retail/commercial); se la
        copertura manca (fallback_level 3), ripiega sui quartieri generici per
        avere comunque nomi d'area. Best-effort: se Overpass non risponde,
        l'analisi resta a livello comune. Solo per modalità con idee.
        """
        if req.modalita not in ("idee", "completa") or not req.comune_nome:
            return None
        try:
            from opendata_core.osm import zones as osm_zones

            async def _work() -> list[dict[str, Any]] | None:
                for tipo in ("commerciale", "quartieri"):
                    out = await osm_zones.list_zones(
                        req.cod_comune, tipo, comune_nome=req.comune_nome
                    )
                    cand = out.get("candidates") or []
                    if cand and out.get("fallback_level") != 3:
                        # Max 2 zone: ogni zona = 1 chiamata Overpass in più; con
                        # l'istanza pubblica che throttla (429), meglio poche.
                        return [
                            {
                                "name": c.get("name"),
                                "centroid": c.get("centroid"),
                                "bbox": c.get("bbox"),
                                "zona_tipo": c.get("zona_tipo", tipo),
                            }
                            for c in cand[:2]
                        ]
                return None

            # Due list_zones in sequenza (Overpass + eventuale fallback Nominatim):
            # rete di sicurezza così la lente non resta appesa oltre il ceiling.
            return await asyncio.wait_for(_work(), timeout=_LENS_SAFETY_TIMEOUT)
        except Exception as exc:
            _log_lens_skip("zone commerciali non risolte per %s — gap commercio a livello comune",
                           req.cod_comune, exc=exc)
            return None

    @staticmethod
    async def _resolve_commercio(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Ancora COMMERCIO con cache Redis 24h (vedi `_lens_cached`)."""
        if req.modalita not in ("idee", "completa"):
            return None
        return await _lens_cached(
            ("commercio", req.cod_comune),
            lambda: OrchestratorSession._resolve_commercio_uncached(req),
        )

    @staticmethod
    async def _resolve_commercio_uncached(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Ancora COMMERCIO deterministica: imprese/UL+addetti ISTAT ASIA del comune.

        L'agente ISTAT (LLM) si è dimostrato inaffidabile nel far emergere questo
        dato (chiama il tool ma non lo riporta nella sezione). Lo recuperiamo qui,
        server-side, e lo iniettiamo nel task — come già si fa per zona/popolazione
        — così l'idee_agent ha SEMPRE l'evidenza imprese + il source_url da citare
        per ancorare un'idea-DUC. Best-effort: se ISTAT non risponde, l'analisi
        resta senza ancora commercio (la lente si salta, non si inventa). Solo per
        modalità con idee.
        """
        if req.modalita not in ("idee", "completa"):
            return None
        try:
            from opendata_core.sdmx import fetch_imprese_comune

            res = await asyncio.wait_for(
                fetch_imprese_comune(req.cod_comune), timeout=30.0
            )
            return res if res and res.get("trovato") else None
        except Exception as exc:
            _log_lens_skip("ancora commercio ISTAT ASIA non risolta per %s — lente commercio assente",
                           req.cod_comune, exc=exc)
            return None

    @staticmethod
    async def _resolve_turismo(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Ancora TURISMO con cache Redis 24h (vedi `_lens_cached`)."""
        if req.modalita not in ("idee", "completa") or not req.comune_nome:
            return None
        return await _lens_cached(
            ("turismo2", req.cod_comune, req.comune_nome or ""),
            lambda: OrchestratorSession._resolve_turismo_uncached(req),
        )

    @staticmethod
    async def _resolve_turismo_uncached(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Ancora TURISMO/CULTURA deterministica: asset culturali OSM + ricettività ISTAT.

        Due ancore complementari, recuperate IN PARALLELO e indipendenti:
        - OSM (geocode→bbox): conteggi POI culturali + poli NOMINATI (per nominare
          un asset da valorizzare); host openstreetmap.org.
        - ISTAT (dataflow 122_54): posti letto + esercizi ricettivi del comune —
          ancora AFFIDABILE/cache-ata che misura la capacità di accoglienza; host
          istat.it. Entrambi citabili (guardrail `_TURISMO_HOSTS`).
        Best-effort: ciascuna fonte degrada da sola; se TUTTE e due falliscono la
        lente si salta (non si inventa). Solo idee/completa.
        """
        if req.modalita not in ("idee", "completa") or not req.comune_nome:
            return None

        from opendata_core.osm import client as osm_client
        from opendata_core.sdmx import fetch_ricettivita_comune

        async def _osm() -> dict[str, Any] | None:
            hits = await osm_client.geocode(f"{req.comune_nome}, Italia", limit=1)
            if not hits:
                return None
            bb = hits[0].get("boundingbox") or []
            if len(bb) != 4:
                return None
            # Nominatim boundingbox = [south, north, west, east]
            s, n, w, e = (float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3]))
            bbox = (s, w, n, e)
            counts = await osm_client.overpass_tourism_counts(bbox=bbox)
            landmarks = await osm_client.overpass_tourism_landmarks(bbox=bbox, limit=12)
            if not counts or counts.get("totale", 0) == 0:
                return None
            clat, clon = (s + n) / 2, (w + e) / 2
            return {
                "counts": counts,
                "landmarks": landmarks[:6],
                "source_url": _osm_object_url(hits[0], clat, clon),
            }

        async def _guard(coro, label: str):  # noqa: ANN001, ANN202
            try:
                return await asyncio.wait_for(coro, timeout=40.0)
            except Exception as exc:
                _log_lens_skip(f"ancora turismo {label} non risolta per %s",
                               req.cod_comune, exc=exc)
                return None

        osm_res, ric = await asyncio.gather(
            _guard(_osm(), "OSM"),
            _guard(fetch_ricettivita_comune(req.cod_comune), "ISTAT ricettività"),
        )
        ricettivita = ric if (ric and ric.get("trovato")) else None
        if not osm_res and not ricettivita:
            return None

        out: dict[str, Any] = {"comune": req.cod_comune}
        if osm_res:
            out.update(osm_res)
        if ricettivita:
            out["ricettivita"] = {
                "anno": ricettivita.get("anno"),
                "posti_letto": ricettivita.get("posti_letto"),
                "esercizi": ricettivita.get("esercizi"),
                "camere": ricettivita.get("camere"),
                "source_url": ricettivita.get("source_url"),
            }
        return out

    @staticmethod
    async def _resolve_lavoro(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Ancora LAVORO con cache Redis 24h (vedi `_lens_cached`)."""
        if req.modalita not in ("idee", "completa"):
            return None
        return await _lens_cached(
            ("lavoro", req.cod_comune),
            lambda: OrchestratorSession._resolve_lavoro_uncached(req),
        )

    @staticmethod
    async def _resolve_lavoro_uncached(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Ancora LAVORO/COMPETENZE deterministica: indicatori occupazionali comunali
        da ISTAT 8milaCensus (censimento 2011). Disoccupazione (anche giovanile), NEET,
        struttura settoriale/competenze. Dato STRUTTURALE 2011 (l'occupazione residente
        comunale non esiste via SDMX). Best-effort: 8milaCensus giù → lente saltata.
        """
        try:
            from opendata_core.census import fetch_lavoro_comune

            res = await asyncio.wait_for(fetch_lavoro_comune(req.cod_comune), timeout=40.0)
            return res if res and res.get("trovato") else None
        except Exception as exc:
            _log_lens_skip("ancora lavoro 8milaCensus non risolta per %s",
                           req.cod_comune, exc=exc)
            return None

    @staticmethod
    async def _resolve_trasporti(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Ancora TRASPORTI con cache Redis 24h (vedi `_lens_cached`)."""
        if req.modalita not in ("idee", "completa") or not req.comune_nome:
            return None
        return await _lens_cached(
            ("trasporti", req.cod_comune, req.comune_nome or ""),
            lambda: OrchestratorSession._resolve_trasporti_uncached(req),
        )

    @staticmethod
    async def _resolve_trasporti_uncached(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Ancora TRASPORTI/MOBILITÀ deterministica: densità OSM del trasporto pubblico
        (fermate bus, autostazioni, stazioni ferroviarie, tram/metro). Misura il servizio
        TPL e la presenza di un nodo ferroviario — criticità accessibilità/dipendenza auto.
        Best-effort: se Nominatim/Overpass non rispondono la lente si salta. Solo
        idee/completa. (GTFS/mobility_node resta complemento futuro: ETL non popolato.)
        """
        try:
            from opendata_core.osm import client as osm_client

            async def _work() -> dict[str, Any] | None:
                hits = await osm_client.geocode(f"{req.comune_nome}, Italia", limit=1)
                if not hits:
                    return None
                bb = hits[0].get("boundingbox") or []
                if len(bb) != 4:
                    return None
                s, n, w, e = (float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3]))
                counts = await osm_client.overpass_transport_counts(bbox=(s, w, n, e))
                if not counts or counts.get("totale", 0) == 0:
                    return None
                clat, clon = (s + n) / 2, (w + e) / 2
                return {
                    "comune": req.cod_comune,
                    "counts": counts,
                    "ha_stazione_treno": counts.get("stazioni_treno", 0) > 0,
                    "source_url": _osm_object_url(hits[0], clat, clon),
                }

            return await asyncio.wait_for(_work(), timeout=40.0)
        except Exception as exc:
            _log_lens_skip("ancora trasporti OSM non risolta per %s",
                           req.cod_comune, exc=exc)
            return None

    @staticmethod
    async def _resolve_welfare(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Ancora WELFARE con cache Redis 24h (vedi `_lens_cached`)."""
        if req.modalita not in ("idee", "completa"):
            return None
        return await _lens_cached(
            ("welfare", req.cod_comune),
            lambda: OrchestratorSession._resolve_welfare_uncached(req),
        )

    @staticmethod
    async def _resolve_welfare_uncached(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Ancora WELFARE/COESIONE SOCIALE deterministica: indici demografici di
        fragilità del comune da ISTAT 8milaCensus (struttura della popolazione,
        Censimento 2011) — l'unica fonte realmente COMUNALE (DCIS_POPRES1 copre solo
        Italia/regioni/province). Indice di vecchiaia, dipendenza anziani/giovanile/
        strutturale, % 75+ — misurano il carico sui servizi socio-assistenziali.
        Arricchita (best-effort) con gli investimenti OpenCoesione del tema
        'inclusione-sociale' del comune, così un'idea welfare ha anche il lato
        finanziamento citabile. Se l'ancora manca, la lente si salta (non si
        inventa). Solo idee/completa.
        """
        if req.modalita not in ("idee", "completa"):
            return None
        try:
            from opendata_core.census import fetch_welfare_comune

            res = await asyncio.wait_for(
                fetch_welfare_comune(req.cod_comune), timeout=30.0
            )
        except Exception as exc:
            _log_lens_skip("ancora welfare ISTAT POPRES1 non risolta per %s — lente welfare assente",
                           req.cod_comune, exc=exc)
            return None
        if not (res and res.get("trovato")):
            return None
        inv = await OrchestratorSession._welfare_investimenti_sociali(req.cod_comune)
        return {**res, "investimenti_sociali": inv} if inv else res

    @staticmethod
    async def _welfare_investimenti_sociali(cod_comune: str) -> dict[str, Any] | None:
        """Investimenti OpenCoesione del tema 'inclusione-sociale' del comune (best-effort).

        Complemento finanziario della lente Welfare: finanziato/pagato/spend-ratio +
        progetti sul sociale, con source_url citabile. Fail-safe: se OpenCoesione non
        ha dati sul tema (o non risponde) l'arricchimento manca, la lente resta valida
        sui soli indici ISTAT.
        """
        try:
            from opendata_core.opencoesione import OpenCoesioneClient

            async with OpenCoesioneClient() as c:
                fc = await asyncio.wait_for(
                    c.funding_capacity(cod_comune=cod_comune, tema="inclusione-sociale"),
                    timeout=30.0,
                )
            return {
                "finanziato_totale": fc.finanziato_totale,
                "pagamenti_totali": fc.pagamenti_totali,
                "spend_ratio": fc.spend_ratio,
                "progetti_totali": fc.progetti_totali,
                "source_url": fc.source_url,
            }
        except Exception as exc:
            _log_lens_skip("investimenti sociali OpenCoesione non risolti per %s",
                           cod_comune, exc=exc)
            return None

    @staticmethod
    async def _resolve_comparabili(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Comparabili peer con cache Redis 24h (vedi `_lens_cached`)."""
        if req.modalita not in ("idee", "completa"):
            return None
        return await _lens_cached(
            ("comparabili", req.cod_comune),
            lambda: OrchestratorSession._resolve_comparabili_uncached(req),
        )

    @staticmethod
    async def _resolve_comparabili_uncached(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Progetti comparabili REALI da comuni della STESSA PROVINCIA (OpenCoesione):
        i 'comuni simili l'hanno fatto' del generatore gap_comparativo. Senza questa
        iniezione il bundle ha solo i dati del comune in esame e l'LLM INVENTAVA i
        comparabili (CLP/importi/esiti — visto in produzione). Prendiamo i progetti
        della provincia (escluso il comune stesso, best-effort per nome/codice),
        ordinati per importo decrescente, top 5, con URL `/progetti/{clp}` citabile.
        Fail-safe: se OpenCoesione non risponde, niente comparabili (l'idea resta
        generica, niente invenzioni). Solo idee/completa.
        """
        cod = (req.cod_comune or "").strip()
        if len(cod) < 3:
            return None
        cod_prov = cod[:3]
        try:
            from opendata_core.opencoesione import OpenCoesioneClient

            async with OpenCoesioneClient() as c:
                res = await asyncio.wait_for(
                    c.search_projects(cod_provincia=cod_prov, limit=50),
                    timeout=30.0,
                )
        except Exception as exc:
            _log_lens_skip("comparabili peer OpenCoesione non risolti per provincia %s",
                           cod_prov, exc=exc)
            return None
        nome = (req.comune_nome or "").strip().lower()

        def _is_self(p: dict[str, Any]) -> bool:
            terr = " ".join(str(t) for t in (p.get("territori") or [])).lower()
            return (nome and nome in terr) or (cod in terr)

        peers = [
            p for p in (res.get("results") or [])
            if p.get("clp") and (p.get("finanziamento_totale") or 0) > 0 and not _is_self(p)
        ]
        peers.sort(key=lambda p: p.get("finanziamento_totale") or 0, reverse=True)
        progetti = [
            {
                "clp": str(p["clp"]).strip(),
                "titolo": p.get("titolo") or "(senza titolo)",
                "tema": p.get("tema"),
                "importo": p.get("finanziamento_totale"),
                "url": f"https://opencoesione.gov.it/it/progetti/{str(p['clp']).strip().lower()}/",
            }
            for p in peers[:5]
        ]
        return {"cod_provincia": cod_prov, "progetti": progetti} if progetti else None

    @staticmethod
    async def _resolve_istruzione(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Ancora ISTRUZIONE con cache Redis 24h (vedi `_lens_cached`)."""
        if req.modalita not in ("idee", "completa"):
            return None
        return await _lens_cached(
            ("istruzione", req.cod_comune),
            lambda: OrchestratorSession._resolve_istruzione_uncached(req),
        )

    @staticmethod
    async def _resolve_istruzione_uncached(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Ancora ISTRUZIONE deterministica da DUE fonti complementari: OFFERTA
        scolastica (MIUR Open Data, anagrafe scuole + alunni; join ISTAT→catastale) +
        GRADO DI ISTRUZIONE della popolazione (ISTAT 8milaCensus, Censimento 2011: %
        laureati/diplomati/licenza media/analfabeti — gli esiti, il capitale umano).
        Best-effort su entrambe: la lente esiste se almeno una ha dati. Solo idee/completa.
        """
        if req.modalita not in ("idee", "completa"):
            return None
        scuole = await OrchestratorSession._istruzione_scuole(req)
        grado = await OrchestratorSession._istruzione_grado(req)
        if not scuole and not grado:
            return None
        result: dict[str, Any] = dict(scuole) if scuole else {
            "trovato": True, "comune": req.cod_comune
        }
        if grado:
            result["grado_istruzione"] = grado
        return result

    @staticmethod
    async def _istruzione_scuole(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Offerta scolastica (MIUR Open Data, anagrafe scuole + alunni)."""
        try:
            from opendata_core.miur import fetch_scuole_comune

            res = await asyncio.wait_for(fetch_scuole_comune(req.cod_comune), timeout=90.0)
        except Exception as exc:
            _log_lens_skip("scuole MIUR non risolte per %s", req.cod_comune, exc=exc)
            return None
        return res if (res and res.get("trovato")) else None

    @staticmethod
    async def _istruzione_grado(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Grado di istruzione della popolazione (ISTAT 8milaCensus, Censimento 2011)."""
        try:
            from opendata_core.census import fetch_grado_istruzione_comune

            res = await asyncio.wait_for(
                fetch_grado_istruzione_comune(req.cod_comune), timeout=60.0
            )
        except Exception as exc:
            _log_lens_skip("grado istruzione 8milaCensus non risolto per %s", req.cod_comune, exc=exc)
            return None
        return res if (res and res.get("trovato")) else None

    @staticmethod
    async def _resolve_ambiente(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Ancora AMBIENTE con cache Redis 24h (vedi `_lens_cached`)."""
        if req.modalita not in ("idee", "completa"):
            return None
        return await _lens_cached(
            ("ambiente", req.cod_comune),
            lambda: OrchestratorSession._resolve_ambiente_uncached(req),
        )

    @staticmethod
    async def _resolve_ambiente_uncached(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Ancora AMBIENTE/RISCHIO IDROGEOLOGICO deterministica: pericolosità da
        frana (elevata/molto elevata, P3+P4) e idraulica/alluvioni (scenari P3/P2)
        del comune da ISPRA IdroGEO — quota di territorio e popolazione esposte.
        È l'unica fonte ambientale realmente COMUNALE con API REST (il consumo di
        suolo ISPRA non ha API e l'ambiente urbano ISTAT copre solo i capoluoghi).
        Vincolo di pianificazione: un'idea su aree a rischio elevato va localizzata
        altrove o prevede mitigazione; quote ~0 = assenza di vincolo (anch'essa
        evidenza). Best-effort: se IdroGEO non risponde la lente si salta (non si
        inventa). Solo idee/completa.
        """
        if req.modalita not in ("idee", "completa"):
            return None
        try:
            from opendata_core.ispra import IspraClient

            async def _work() -> Any:
                async with IspraClient() as c:
                    return await c.risk_indicators(req.cod_comune)

            ind = await asyncio.wait_for(_work(), timeout=30.0)
        except Exception as exc:
            _log_lens_skip("ancora ambiente ISPRA IdroGEO non risolta per %s — lente ambiente assente",
                           req.cod_comune, exc=exc)
            return None
        if not ind:
            return None

        def _slice(slices: list[Any], classe: str) -> Any | None:
            return next((s for s in slices if s.classe == classe), None)

        fr = ind.frane_p3p4
        idr_p3 = _slice(ind.idraulica, "p3")
        idr_p2 = _slice(ind.idraulica, "p2")
        return {
            "comune": req.cod_comune,
            "nome": ind.nome,
            "popolazione_residente": ind.popolazione_residente,
            "area_kmq": ind.area_kmq,
            # frane: aggregato pericolosità elevata + molto elevata (P3+P4)
            "frane_area_pct": fr.area_pct if fr else None,
            "frane_pop": fr.popolazione if fr else None,
            "frane_pop_pct": fr.popolazione_pct if fr else None,
            # idraulica/alluvioni: scenario elevato (P3) e medio (P2)
            "alluvioni_p3_area_pct": idr_p3.area_pct if idr_p3 else None,
            "alluvioni_p3_pop_pct": idr_p3.popolazione_pct if idr_p3 else None,
            "alluvioni_p2_area_pct": idr_p2.area_pct if idr_p2 else None,
            "alluvioni_p2_pop": idr_p2.popolazione if idr_p2 else None,
            "alluvioni_p2_pop_pct": idr_p2.popolazione_pct if idr_p2 else None,
            "livello": "comunale",
            "source_url": ind.source_url,
            "trovato": True,
        }

    @staticmethod
    async def _resolve_sanita(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Ancora SANITÀ con cache Redis 24h (vedi `_lens_cached`)."""
        if req.modalita not in ("idee", "completa"):
            return None
        return await _lens_cached(
            ("sanita", req.cod_comune),
            lambda: OrchestratorSession._resolve_sanita_uncached(req),
        )

    @staticmethod
    async def _resolve_sanita_uncached(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Ancora SANITÀ deterministica: dotazione sanitaria del comune da DUE fonti
        complementari — FARMACIE (Min. Salute/NSIS, join per codice ISTAT, presidio
        di prossimità) + PRESÌDI OSM (ospedali e strutture territoriali — ambulatori,
        studi medici — geo-join sul confine comunale). Misura l'accessibilità ai
        servizi sanitari di base e ospedalieri. Best-effort su entrambe: la lente
        esiste se almeno una fonte ha dati. Solo idee/completa.
        """
        if req.modalita not in ("idee", "completa"):
            return None
        farmacie = await OrchestratorSession._sanita_farmacie(req)
        osm = await OrchestratorSession._sanita_osm_strutture(req)
        if not farmacie and not osm:
            return None
        result: dict[str, Any] = dict(farmacie) if farmacie else {
            "trovato": True, "comune": req.cod_comune
        }
        if osm:
            result.update(osm)
        return result

    @staticmethod
    async def _sanita_farmacie(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Farmacie attive del comune (Min. Salute/NSIS, join per codice ISTAT)."""
        try:
            from opendata_core.salute import fetch_farmacie_comune

            res = await asyncio.wait_for(
                fetch_farmacie_comune(req.cod_comune), timeout=90.0
            )
        except Exception as exc:
            _log_lens_skip("farmacie Min. Salute non risolte per %s", req.cod_comune, exc=exc)
            return None
        return res if (res and res.get("trovato")) else None

    @staticmethod
    async def _sanita_osm_strutture(req: ProgrammaRequest) -> dict[str, Any] | None:
        """Ospedali + strutture territoriali (ambulatori, studi medici) mappati su OSM,
        contati nel bbox del comune. Se il comune NON ha ospedale, calcola
        l'ACCESSIBILITÀ: ospedale più vicino + distanza/tempo in auto (Overpass +
        OSRM, dati live). Best-effort (Nominatim/Overpass/OSRM); richiede `comune_nome`.
        None se né presìdi nel comune né un ospedale raggiungibile."""
        if not req.comune_nome:
            return None
        try:
            from opendata_core.osm import client as osm_client

            async def _work() -> dict[str, Any] | None:
                hits = await osm_client.geocode(f"{req.comune_nome}, Italia", limit=1)
                if not hits:
                    return None
                bb = hits[0].get("boundingbox") or []
                if len(bb) != 4:
                    return None
                s, n, w, e = (float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3]))
                clat, clon = (s + n) / 2, (w + e) / 2
                counts = await osm_client.overpass_health_counts(bbox=(s, w, n, e)) or {}
                ospedali = counts.get("ospedali", 0)
                result: dict[str, Any] = {
                    "ospedali": ospedali,
                    "strutture_territoriali": counts.get("ambulatori", 0)
                    + counts.get("studi_medici", 0),
                    "osm_source_url": _osm_object_url(hits[0], clat, clon),
                }
                # Nessun ospedale nel comune → misura l'accessibilità al più vicino.
                if ospedali == 0:
                    nh = await osm_client.nearest_hospital(clat, clon)
                    if nh:
                        osp = {"nome": nh["nome"], "dist_linea_km": nh["dist_linea_km"]}
                        try:
                            route = await osm_client.osrm_route(
                                (clat, clon), (nh["lat"], nh["lon"])
                            )
                            r0 = (route.get("routes") or [{}])[0]
                            if r0.get("distance") is not None:
                                osp["distanza_km"] = round(r0["distance"] / 1000, 1)
                                osp["durata_min"] = round(r0["duration"] / 60)
                        except Exception:
                            pass  # routing best-effort: resta la distanza in linea d'aria
                        result["ospedale_piu_vicino"] = osp
                # La lente OSM esiste se c'è almeno un presidio nel comune o un
                # ospedale vicino raggiungibile (il caso "comune senza nulla" è informativo).
                if counts.get("totale", 0) == 0 and "ospedale_piu_vicino" not in result:
                    return None
                return result

            return await asyncio.wait_for(_work(), timeout=60.0)
        except Exception as exc:
            _log_lens_skip("presìdi sanitari OSM non risolti per %s", req.cod_comune, exc=exc)
            return None

    async def _resolve_all_lenses(
        self,
        req: ProgrammaRequest,
        *,
        emit: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Risolve TUTTE le lenti in PARALLELO (zona, zone commerciali, commercio,
        turismo, lavoro, trasporti, welfare, istruzione, ambiente, sanita).

        Prima erano awaited in sequenza: con timeout per-lente di 30-40s la somma
        dominava la latenza dell'analisi (path critico ~150-200s). In parallelo il
        costo passa da SOMMA a MAX. Ogni lente è già fail-safe (ritorna None su
        errore); qui isoliamo anche le eccezioni impreviste, così una lente che
        esplode non affonda le altre.

        Se `emit` è fornito, OGNI lente pubblica un evento `status` start/end
        appena parte/conclude — con `elapsed_ms` e l'esito (None ⇒ `error`:
        "nessun dato", marcata "–" dalla UI). Così la fase "evidenze territoriali"
        diventa una checklist live delle 10 lenti invece di una barra opaca.
        """
        lenses: list[tuple[str, Any]] = [
            ("zona", self._resolve_zona(req)),
            ("zone_comm", self._resolve_zone_commerciali(req)),
            ("commercio", self._resolve_commercio(req)),
            ("turismo", self._resolve_turismo(req)),
            ("lavoro", self._resolve_lavoro(req)),
            ("trasporti", self._resolve_trasporti(req)),
            ("welfare", self._resolve_welfare(req)),
            ("istruzione", self._resolve_istruzione(req)),
            ("ambiente", self._resolve_ambiente(req)),
            ("sanita", self._resolve_sanita(req)),
            ("comparabili", self._resolve_comparabili(req)),
        ]
        loop = asyncio.get_event_loop()

        async def _run(key: str, coro: Any) -> tuple[str, Any]:
            src = _LENS_SOURCES.get(key, key)
            if emit is not None:
                emit({"event": "status", "source": src, "phase": "start"})
            t0 = loop.time()
            result: Any = None
            try:
                result = await coro
            except Exception as exc:  # noqa: BLE001 — isola la lente (CancelledError risale)
                log.warning("resolver lente %s fallito (isolato): %s", key, exc)
                result = None
            if emit is not None:
                ev: dict[str, Any] = {
                    "event": "status", "source": src, "phase": "end",
                    "elapsed_ms": int((loop.time() - t0) * 1000),
                }
                if result is None:  # nessun dato → la UI marca "–" (saltata, non errore)
                    ev["error"] = "nessun dato"
                emit(ev)
            return key, result

        pairs = await asyncio.gather(*(_run(k, c) for k, c in lenses))
        out = dict(pairs)
        return {k: out[k] for k in (
            "zona", "zone_comm", "commercio", "turismo", "lavoro", "trasporti",
            "welfare", "istruzione", "ambiente", "sanita", "comparabili",
        )}

    async def run_programma_streaming(
        self,
        req: ProgrammaRequest,
        *,
        heartbeat_sec: float = 10.0,
        total_timeout_sec: float = 900.0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Come `run_programma`, ma con eventi di avanzamento GRANULARI.

        Oltre allo start/end per fonte (pattern di `run_streaming`), un
        logging-handler intercetta i record del framework sugli strumenti
        ("Function name: X" / "Function X succeeded") e li rilancia come
        eventi `tool` — ogni chiamata MCP è visibile nella UI.

        Eventi:
            {"event":"status","source":"<fonte>","phase":"start|end","error"?}
            {"event":"tool","name":"<tool>","phase":"start|end|error"}
            {"event":"heartbeat","in_flight":[...],"elapsed_ms":int}
            {"event":"result","scheda":{...}}   # ultimo, una volta sola
            {"event":"error","message":str}
        """
        if not self._participants:
            raise RuntimeError("OrchestratorSession not entered")
        if self._programma_agent is None:
            raise RuntimeError("Programma disabilitato (enable_programma=false)")
        # S1 — primo byte IMMEDIATO: la raccolta evidenze è una fase visibile e
        # parte subito, in PARALLELO (P1), con heartbeat finché è in corso. Prima i
        # 6 resolver giravano in sequenza PRIMA di qualsiasi evento → schermo vuoto
        # per ~150-200s. I resolver restano fuori dal lock (indipendenti, cache-ati).
        yield {"event": "status", "source": "evidenze territoriali", "phase": "start"}
        t_lens = asyncio.get_event_loop().time()
        # P1 con visibilità per-lente: ogni lente pubblica start/end sulla coda
        # man mano che parte/conclude → la UI mostra la checklist live delle 10
        # lenti, non più un'unica barra ferma per minuti.
        lens_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        lens_task = asyncio.create_task(
            self._resolve_all_lenses(req, emit=lens_queue.put_nowait)
        )
        while not lens_task.done() or not lens_queue.empty():
            try:
                ev = await asyncio.wait_for(lens_queue.get(), timeout=heartbeat_sec)
            except asyncio.TimeoutError:
                if not lens_task.done():
                    yield {
                        "event": "heartbeat",
                        "in_flight": ["evidenze territoriali"],
                        "elapsed_ms": int((asyncio.get_event_loop().time() - t_lens) * 1000),
                    }
                continue
            yield ev
        lenses = await lens_task
        yield {"event": "status", "source": "evidenze territoriali", "phase": "end"}

        async with self._lock:
            aggregator = build_programma_aggregator(
                self._programma_agent, req,
                idee_agent=self._idee_agent,
                # Marketing nell'analisi unica solo se la fonte web è attiva
                # (senza, gli spunti non avrebbero l'ispirazione esterna e
                # verrebbero scartati dal guardrail A+B).
                marketing_agent=self._marketing_agent if self._settings.enable_web else None,
                commercio_info=lenses["commercio"],
                turismo_info=lenses["turismo"],
                lavoro_info=lenses["lavoro"],
                trasporti_info=lenses["trasporti"],
                welfare_info=lenses["welfare"],
                istruzione_info=lenses["istruzione"],
                ambiente_info=lenses["ambiente"],
                sanita_info=lenses["sanita"],
                comparabili_info=lenses["comparabili"],
                idee_chunking=self._settings.idee_chunking,
            )
            task_text = build_programma_task(
                req, lenses["zona"], lenses["zone_comm"], lenses["commercio"],
                lenses["turismo"], lenses["lavoro"], lenses["trasporti"],
                welfare_info=lenses["welfare"],
                istruzione_info=lenses["istruzione"],
                ambiente_info=lenses["ambiente"],
                sanita_info=lenses["sanita"],
            )
            queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
            in_flight: set[str] = set()
            t0 = asyncio.get_event_loop().time()

            class _ToolEventHandler(logging.Handler):
                """Rilancia i log del framework come eventi tool sulla coda."""

                def emit(self, record: logging.LogRecord) -> None:
                    try:
                        msg = record.getMessage()
                    except Exception:  # pragma: no cover — record malformato
                        return
                    ev: dict[str, Any] | None = None
                    if msg.startswith("Function name: "):
                        ev = {"event": "tool", "name": msg.removeprefix("Function name: ").strip(),
                              "phase": "start"}
                    elif msg.startswith("Function ") and msg.rstrip(".").endswith("succeeded"):
                        name = msg.removeprefix("Function ").split(" ")[0]
                        ev = {"event": "tool", "name": name, "phase": "end"}
                    elif msg.startswith("Function failed"):
                        ev = {"event": "tool", "name": "", "phase": "error"}
                    if ev is not None:
                        try:
                            queue.put_nowait(ev)
                        except Exception:  # pragma: no cover — coda piena
                            pass

            handler = _ToolEventHandler(level=logging.INFO)
            fw_logger = logging.getLogger("agent_framework")
            fw_logger.addHandler(handler)

            per_specialist = self._settings.specialist_timeout_sec

            async def _worker(agent: Agent) -> _WrappedAgentResult:
                name = getattr(agent, "name", None) or "agent"
                in_flight.add(name)
                await queue.put({"event": "status", "source": name, "phase": "start"})
                try:
                    # Timeout PER SPECIALISTA: uno specialista lento (es. CKAN che
                    # ritenta download 404) non deve bloccare l'intero report —
                    # scaduto, viene escluso e gli altri proseguono.
                    resp = await asyncio.wait_for(agent.run(task_text), timeout=per_specialist)
                except asyncio.TimeoutError:
                    in_flight.discard(name)
                    await queue.put({
                        "event": "status", "source": name, "phase": "end",
                        "error": f"timeout dopo {int(per_specialist)}s",
                    })
                    raise
                except Exception as exc:
                    in_flight.discard(name)
                    await queue.put(
                        {"event": "status", "source": name, "phase": "end", "error": str(exc)}
                    )
                    raise
                in_flight.discard(name)
                await queue.put({"event": "status", "source": name, "phase": "end"})
                return _WrappedAgentResult(executor_id=name, agent_response=resp)

            tasks = [asyncio.create_task(_worker(p)) for p in self._participants]

            async def _drain_then_sentinel() -> list[Any]:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                await queue.put(None)
                return results

            collector = asyncio.create_task(_drain_then_sentinel())
            deadline = t0 + total_timeout_sec
            timed_out = False

            try:
                while True:
                    now = asyncio.get_event_loop().time()
                    remaining = deadline - now
                    if remaining <= 0:
                        timed_out = True
                        break
                    wait = min(heartbeat_sec, remaining)
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=wait)
                    except asyncio.TimeoutError:
                        if in_flight:
                            elapsed_ms = int((asyncio.get_event_loop().time() - t0) * 1000)
                            yield {
                                "event": "heartbeat",
                                "in_flight": sorted(in_flight),
                                "elapsed_ms": elapsed_ms,
                            }
                        continue
                    if event is None:
                        break
                    yield event

                if timed_out:
                    yield {
                        "event": "error",
                        "message": (
                            f"Timeout dopo {int(total_timeout_sec)}s. Fonti ancora attive: "
                            f"{', '.join(sorted(in_flight)) or '—'}."
                        ),
                    }
                    return

                results = await collector
                real_results = [r for r in results if not isinstance(r, BaseException)]

                fase = "report completo" if req.modalita == "completa" else req.modalita
                yield {"event": "status", "source": "sintesi", "phase": "start",
                       "detail": fase}
                # L3+U1: la sintesi gira come TASK che streama i token degli agenti
                # (programma/idee/marketing) sulla coda via `emit`; qui consumiamo la
                # coda finché è in corso, così il feed "thinking" è live (prima la
                # sintesi era un await opaco → UI ferma per minuti).
                synth_task = asyncio.create_task(
                    aggregator(real_results, emit=queue.put_nowait)
                )
                try:
                    while not synth_task.done():
                        try:
                            event = await asyncio.wait_for(queue.get(), timeout=heartbeat_sec)
                        except asyncio.TimeoutError:
                            yield {
                                "event": "heartbeat", "in_flight": ["sintesi"],
                                "elapsed_ms": int((asyncio.get_event_loop().time() - t0) * 1000),
                            }
                            continue
                        if event is not None:
                            yield event
                    while not queue.empty():  # drena gli eventi residui di fine sintesi
                        ev = queue.get_nowait()
                        if ev is not None:
                            yield ev
                    output = await synth_task
                except Exception as exc:
                    log.exception("programma aggregator failed in streaming")
                    yield {"event": "status", "source": "sintesi", "phase": "end",
                           "error": str(exc)}
                    yield {"event": "error", "message": f"Sintesi fallita: {exc}"}
                    return
                yield {"event": "status", "source": "sintesi", "phase": "end"}

                resp = getattr(output, "response", None)
                if not isinstance(resp, ProgrammaResponse):
                    resp = ProgrammaResponse.model_validate_json(
                        getattr(output, "text", None) or str(output)
                    )
                yield {"event": "result", "scheda": resp.model_dump(mode="json")}
            finally:
                fw_logger.removeHandler(handler)
                for t in tasks:
                    if not t.done():
                        t.cancel()
                if not collector.done():
                    collector.cancel()
                await asyncio.gather(*tasks, collector, return_exceptions=True)

    async def run_programma(self, req: ProgrammaRequest) -> ProgrammaResponse:
        """Fan-out delle evidenze sul comune + sintesi strutturata della scheda.

        Stessi partecipanti di `run()`, aggregatore dedicato (programma) al
        posto del synth. Serializzato con lo stesso lock: workflow single-shot
        e agenti condivisi.
        """
        if not self._participants:
            raise RuntimeError("OrchestratorSession not entered")
        if self._programma_agent is None:
            raise RuntimeError("Programma disabilitato (enable_programma=false)")
        lenses = await self._resolve_all_lenses(req)  # P1: lenti in parallelo
        async with self._lock:
            # L'aggregatore riceve entrambi gli agenti: la modalità decide se
            # usarne uno solo (scheda/idee) o fonderli (completa).
            aggregator = build_programma_aggregator(
                self._programma_agent, req,
                idee_agent=self._idee_agent,
                # Marketing nell'analisi unica solo se la fonte web è attiva
                # (senza, gli spunti non avrebbero l'ispirazione esterna e
                # verrebbero scartati dal guardrail A+B).
                marketing_agent=self._marketing_agent if self._settings.enable_web else None,
                commercio_info=lenses["commercio"],
                turismo_info=lenses["turismo"],
                lavoro_info=lenses["lavoro"],
                trasporti_info=lenses["trasporti"],
                welfare_info=lenses["welfare"],
                istruzione_info=lenses["istruzione"],
                ambiente_info=lenses["ambiente"],
                sanita_info=lenses["sanita"],
                comparabili_info=lenses["comparabili"],
                idee_chunking=self._settings.idee_chunking,
            )
            workflow = build_workflow(self._participants, aggregator)
            events = await workflow.run(
                build_programma_task(
                    req, lenses["zona"], lenses["zone_comm"], lenses["commercio"],
                    lenses["turismo"], lenses["lavoro"], lenses["trasporti"],
                    welfare_info=lenses["welfare"],
                    istruzione_info=lenses["istruzione"],
                    ambiente_info=lenses["ambiente"],
                    sanita_info=lenses["sanita"],
                )
            )
        outputs = events.get_outputs()
        if not outputs:
            raise RuntimeError("Programma workflow produced no outputs")
        final = outputs[0]
        response = getattr(final, "response", None)
        if isinstance(response, ProgrammaResponse):
            return response
        # Fallback: il workflow ha serializzato l'output → riparsa dal JSON.
        text = getattr(final, "text", None) or str(final)
        return ProgrammaResponse.model_validate_json(text)

    async def run(self, query: str) -> str:
        """Fan out `query` to the enabled specialists in parallel and return the synth reply.

        Builds a fresh workflow per call and serialises calls with a lock: the
        agent-framework workflow object rejects concurrent / repeat executions,
        and the participant Agents are shared across requests.
        """
        if not self._participants or self._synth_agent is None:
            raise RuntimeError("OrchestratorSession not entered")
        async with self._lock:
            aggregator = build_aggregator(self._synth_agent, user_query=query)
            workflow = build_workflow(self._participants, aggregator)
            events = await workflow.run(query)
        outputs = events.get_outputs()
        if not outputs:
            raise RuntimeError("Orchestrator workflow produced no outputs")
        # Aggregator returns a single AgentResponse-like; extract its text.
        final = outputs[0]
        text = getattr(final, "text", None)
        if text is None:
            messages = getattr(final, "messages", None)
            if messages:
                text = getattr(messages[-1], "text", None)
        return text if text is not None else str(final)

    async def run_streaming(
        self,
        query: str,
        *,
        sources: set[str] | None = None,
        heartbeat_sec: float = 10.0,
        total_timeout_sec: float = 600.0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Same fan-out as `run()`, but yields status events as the work progresses.

        Bypasses the agent-framework workflow (which is opaque) to keep direct
        control of per-participant entry/exit. The aggregator is still reused so
        downstream parsing matches `run()` exactly.

        Yields dicts shaped:
            {"event": "status",    "source": "<name>", "phase": "start|end", "error"?: str}
            {"event": "heartbeat", "in_flight": ["istat", ...], "elapsed_ms": int}
            {"event": "result",    "text": str}     # last, exactly once
            {"event": "error",     "message": str}  # only on fatal failure
        """
        if not self._participants or self._synth_agent is None:
            raise RuntimeError("OrchestratorSession not entered")

        # The same lock as run(): participant Agents are shared across requests
        # and the underlying MCP sessions don't tolerate concurrent reuse.
        async with self._lock:
            aggregator = build_aggregator(self._synth_agent, user_query=query)

            # Source scoping (esplora): fan out to a subset only — a "find me the
            # data" query needs CKAN + SDMX, not OpenCoesione/ISPRA/OSM/web. Fewer
            # sources = faster AND avoids the heavy ones crowding out / timing out
            # CKAN (the regression where the map went empty). Falls back to all if
            # the filter matches nothing.
            participants = self._participants
            if sources:
                scoped = [
                    p for p in participants
                    if (_normalise_source_tag(getattr(p, "name", "") or "") or "") in sources
                ]
                excluded = [
                    getattr(p, "name", "?") for p in participants if p not in scoped
                ]
                if scoped:
                    participants = scoped
                    if excluded:
                        log.info(
                            "run_streaming scope=%s → %d/%d participants (excluded: %s)",
                            sorted(sources), len(scoped), len(self._participants),
                            ", ".join(excluded),
                        )
                else:
                    log.warning(
                        "run_streaming: scope %s matched no participant; using all %d",
                        sorted(sources), len(self._participants),
                    )

            queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
            in_flight: set[str] = set()
            t0 = asyncio.get_event_loop().time()

            per_specialist = self._settings.specialist_timeout_sec

            async def _worker(agent: Agent) -> _WrappedAgentResult:
                name = getattr(agent, "name", None) or "agent"
                in_flight.add(name)
                await queue.put({"event": "status", "source": name, "phase": "start"})
                try:
                    # Timeout PER SPECIALISTA (vedi run_programma_streaming): uno
                    # specialista lento non blocca l'intero fan-out.
                    resp = await asyncio.wait_for(agent.run(query), timeout=per_specialist)
                except asyncio.TimeoutError:
                    in_flight.discard(name)
                    await queue.put({
                        "event": "status", "source": name, "phase": "end",
                        "error": f"timeout dopo {int(per_specialist)}s",
                    })
                    raise
                except Exception as exc:
                    in_flight.discard(name)
                    await queue.put(
                        {"event": "status", "source": name, "phase": "end", "error": str(exc)}
                    )
                    raise
                in_flight.discard(name)
                # Partial result (R1): stream this source's narrative as soon as
                # it finishes, so the UI fills progressively instead of waiting
                # for the synth. Best-effort — never block the worker.
                try:
                    p_narr, _ = parse_agent_reply(getattr(resp, "text", None) or "")
                    if p_narr.strip():
                        await queue.put({
                            "event": "partial", "source": name,
                            "narrative": p_narr.strip()[:600],
                        })
                except Exception:  # pragma: no cover — purely cosmetic
                    pass
                await queue.put({"event": "status", "source": name, "phase": "end"})
                return _WrappedAgentResult(executor_id=name, agent_response=resp)

            tasks = [asyncio.create_task(_worker(p)) for p in participants]

            async def _drain_then_sentinel() -> list[Any]:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                await queue.put(None)  # sentinel
                return results

            collector = asyncio.create_task(_drain_then_sentinel())
            deadline = t0 + total_timeout_sec
            timed_out = False

            try:
                while True:
                    now = asyncio.get_event_loop().time()
                    remaining = deadline - now
                    if remaining <= 0:
                        timed_out = True
                        break
                    wait = min(heartbeat_sec, remaining)
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=wait)
                    except asyncio.TimeoutError:
                        # No status changes within `heartbeat_sec` — emit a heartbeat
                        # so the client knows the connection is still alive and which
                        # sources are still running.
                        if in_flight:
                            elapsed_ms = int((asyncio.get_event_loop().time() - t0) * 1000)
                            yield {
                                "event": "heartbeat",
                                "in_flight": sorted(in_flight),
                                "elapsed_ms": elapsed_ms,
                            }
                        continue
                    if event is None:
                        break
                    yield event

                if timed_out:
                    log.warning(
                        "run_streaming hit total_timeout_sec=%s; cancelling %d tasks",
                        total_timeout_sec, len(tasks),
                    )
                    yield {
                        "event": "error",
                        "message": (
                            f"Timeout dopo {int(total_timeout_sec)}s. Sorgenti ancora attive: "
                            f"{', '.join(sorted(in_flight)) or '—'}."
                        ),
                    }
                    return

                results = await collector
                # Bubble up unexpected non-Exception failures the same way run() would.
                real_results = [r for r in results if not isinstance(r, BaseException)]

                # Diagnostics (Fase 3): which sources were dropped (timeout/error)
                # before synth. The "merged 0 resources" regression was a silently
                # dropped CKAN — make it visible.
                dropped = [
                    getattr(p, "name", "?")
                    for p, r in zip(participants, results)
                    if isinstance(r, BaseException)
                ]
                if dropped:
                    log.warning(
                        "run_streaming: %d/%d source(s) dropped before synth: %s",
                        len(dropped), len(participants), ", ".join(dropped),
                    )

                yield {"event": "status", "source": "synth", "phase": "start"}
                # Stream the synth tokens (R2): run the aggregator as a task that
                # emits `thinking` deltas on the shared queue, and drain them live
                # so the answer streams in instead of landing in one burst after a
                # frozen wait. Mirrors run_programma_streaming.
                synth_task = asyncio.create_task(
                    aggregator(real_results, emit=queue.put_nowait)
                )
                try:
                    while not synth_task.done():
                        try:
                            event = await asyncio.wait_for(queue.get(), timeout=heartbeat_sec)
                        except asyncio.TimeoutError:
                            yield {
                                "event": "heartbeat", "in_flight": ["synth"],
                                "elapsed_ms": int((asyncio.get_event_loop().time() - t0) * 1000),
                            }
                            continue
                        if event is not None:
                            yield event
                    while not queue.empty():  # drain trailing synth deltas
                        ev = queue.get_nowait()
                        if ev is not None:
                            yield ev
                    synth_output = await synth_task
                except Exception as exc:
                    log.exception("synth aggregator failed in run_streaming")
                    yield {"event": "status", "source": "synth", "phase": "end", "error": str(exc)}
                    yield {"event": "error", "message": f"Sintesi fallita: {exc}"}
                    return
                yield {"event": "status", "source": "synth", "phase": "end"}

                yield {"event": "result", "text": getattr(synth_output, "text", "") or str(synth_output)}
            finally:
                # Cancel any still-pending participant work so a timed-out or
                # client-aborted request doesn't leak tasks (which would keep
                # the next request waiting on `self._lock`).
                for t in tasks:
                    if not t.done():
                        t.cancel()
                if not collector.done():
                    collector.cancel()
                # Best-effort drain; we don't propagate cancellation exceptions.
                await asyncio.gather(*tasks, collector, return_exceptions=True)


@dataclass
class _WrappedAgentResult:
    """Mirror the AgentExecutorResponse shape consumed by `orchestrator.synth`.

    The aggregator reads `.executor_id` (for source tagging) and
    `.agent_response.messages` (for tool-result capture).
    """

    executor_id: str
    agent_response: Any
