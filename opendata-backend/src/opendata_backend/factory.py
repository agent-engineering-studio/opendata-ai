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
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, AsyncIterator

from agent_framework import Agent, MCPStreamableHTTPTool

from .config import (
    CKAN_INSTRUCTIONS,
    EUROSTAT_INSTRUCTIONS,
    IDEE_INSTRUCTIONS,
    ISPRA_INSTRUCTIONS,
    ISTAT_INSTRUCTIONS,
    KG_INSTRUCTIONS,
    MARKETING_INSTRUCTIONS,
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
from .orchestrator.synth import build_aggregator
from .orchestrator.workflow import build_workflow

log = logging.getLogger("orchestrator.factory")


def build_chat_client(settings: Settings) -> Any:
    """Return a Microsoft Agent Framework chat client for the configured provider."""
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

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
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
                "(enable_ckan / istat / eurostat / oecd / opencoesione / osm / ispra / kg / web)"
            )
        self._enabled_sources = enabled
        log.info(
            "OrchestratorSession starting | provider=%s sources=%s",
            s.llm_provider, ",".join(enabled),
        )

        chat_client = build_chat_client(s)
        default_options: dict[str, object] = {}
        if resolve_provider(s) == "ollama":
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

        synth_agent = await self._enter_agent(
            chat_client, SYNTH_INSTRUCTIONS, s.synth_agent_name, None, synth_options,
        )
        self._synth_agent = synth_agent

        # Agente tool-less della scheda programma (come il synth, istruzioni
        # diverse). Con provider claude può girare su un modello dedicato.
        if s.enable_programma:
            programma_client = chat_client
            if s.programma_model and resolve_provider(s) == "claude":
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
                None, synth_options,
            )
            # Modalità "marketing" (Pezzo 10): stesso client, istruzioni dedicate.
            self._marketing_agent = await self._enter_agent(
                programma_client, MARKETING_INSTRUCTIONS, f"{s.programma_agent_name}-marketing",
                None, synth_options,
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
        """Zona OSM selezionata (Pezzo 6) → {name, centroid, bbox} per il task.

        Best-effort: se Overpass non risponde si procede senza zona risolta
        (l'analisi degrada a livello comune, come da catena di fallback).
        """
        if not req.zona_osm_id:
            return None
        try:
            from opendata_core.osm import zones as osm_zones

            osm_type, _, osm_id = req.zona_osm_id.partition("/")
            feature = await osm_zones.get_zone(osm_type, osm_id or osm_type)
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
        except Exception:
            log.warning("zona OSM %s non risolta — procedo a livello comune",
                        req.zona_osm_id, exc_info=True)
            return None

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
        zona_info = await self._resolve_zona(req)

        async with self._lock:
            aggregator = build_programma_aggregator(
                self._programma_agent, req,
                idee_agent=self._idee_agent, marketing_agent=self._marketing_agent
            )
            task_text = build_programma_task(req, zona_info)
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
                try:
                    output = await aggregator(real_results)
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
        zona_info = await self._resolve_zona(req)
        async with self._lock:
            # L'aggregatore riceve entrambi gli agenti: la modalità decide se
            # usarne uno solo (scheda/idee) o fonderli (completa).
            aggregator = build_programma_aggregator(
                self._programma_agent, req,
                idee_agent=self._idee_agent, marketing_agent=self._marketing_agent
            )
            workflow = build_workflow(self._participants, aggregator)
            events = await workflow.run(build_programma_task(req, zona_info))
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
                await queue.put({"event": "status", "source": name, "phase": "end"})
                return _WrappedAgentResult(executor_id=name, agent_response=resp)

            tasks = [asyncio.create_task(_worker(p)) for p in self._participants]

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

                yield {"event": "status", "source": "synth", "phase": "start"}
                try:
                    synth_output = await aggregator(real_results)
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
