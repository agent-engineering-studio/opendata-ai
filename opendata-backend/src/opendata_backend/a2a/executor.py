"""A2A AgentExecutor that dispatches incoming requests to our orchestrator.

Phase 1 (this file): protocol-level scaffolding only. Each skill returns a
stub completion so we can verify the A2A round-trip end-to-end (task lifecycle,
artifact, terminal status).

Phase 2 will wire the real `_run_orchestrator` / `classify_dataset` paths in.
"""

from __future__ import annotations

import json
import logging

from a2a.helpers import (
    get_message_text,
    new_task_from_user_message,
    new_text_message,
    new_text_part,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types.a2a_pb2 import TaskState

from ..orchestrator.parsing import (
    fill_missing_content,
    parse_agent_reply,
    upgrade_sdmx_resources,
)
from ..osm_map import attach_maps
from ..state import session_holder
from .agent_card import SKILL_CLASSIFY, SKILL_GEO, SKILL_SEARCH

log = logging.getLogger("opendata-backend.a2a")

_KNOWN_SKILLS = {SKILL_SEARCH, SKILL_GEO, SKILL_CLASSIFY}

# Geographic format set used to filter resources for the find_geo_resources skill.
# Mirrors the UI-side conversion in opendata-ai-ui/lib/geoConvert.ts.
_GEO_FORMATS = {"GEOJSON", "KML", "GPX", "SHP", "WMS", "WFS", "GPKG", "KMZ"}

_MAP_MODE_HINT = (
    "MAP_MODE: l'utente sta visualizzando una mappa. PREFERISCI risorse "
    "geografiche (GeoJSON, Shapefile, KML, GPX, WMS) e confini amministrativi "
    "(regioni, province, comuni) quando opportuno. Evita risorse puramente "
    "tabulari (CSV / JSON di valori) se sono disponibili alternative geografiche."
)


def _wrap_query(query: str, *, prefer_geo: bool) -> str:
    """Same query-prefixing logic as the FastAPI route (datasets.py::_wrap_query)."""
    if not prefer_geo:
        return f"USER QUERY: {query}"
    return f"{_MAP_MODE_HINT}\nUSER QUERY: {query}"


def _resolve_skill(context: RequestContext) -> str:
    """Pick the skill id from the message metadata; default to `search_open_data`.

    A2A messages carry an optional `metadata.skill` field by convention — when
    absent we route to the broadest skill so a vanilla A2A client still works.
    """
    msg = context.message
    meta = getattr(msg, "metadata", None) or {}
    if isinstance(meta, dict):
        sk = meta.get("skill")
        if isinstance(sk, str) and sk in _KNOWN_SKILLS:
            return sk
    return SKILL_SEARCH


class OpenDataAgentExecutor(AgentExecutor):
    """Bridge A2A skill invocations onto the existing orchestrator pipeline."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Ensure there is a task object the client can poll / stream against.
        if context.current_task:
            task = context.current_task
        else:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)

        task_updater = TaskUpdater(
            event_queue=event_queue,
            task_id=task.id,
            context_id=task.context_id,
        )
        skill = _resolve_skill(context)
        query = get_message_text(context.message) or ""
        log.info("A2A execute skill=%s query=%r", skill, query[:120])

        if skill == SKILL_CLASSIFY:
            await self._run_classify(context, task_updater, query)
            return

        # search_open_data / find_geo_resources both go through run_streaming;
        # the only difference is the prefer_geo flag and a final geo-only filter.
        await self._run_search(
            task_updater, query, prefer_geo=(skill == SKILL_GEO), geo_only=(skill == SKILL_GEO),
        )

    async def _run_search(
        self,
        task_updater: TaskUpdater,
        query: str,
        *,
        prefer_geo: bool,
        geo_only: bool,
    ) -> None:
        sess = session_holder.session
        settings = session_holder.settings
        if sess is None or settings is None:
            await task_updater.update_status(
                state=TaskState.TASK_STATE_FAILED,
                message=new_text_message("Backend session non inizializzata."),
            )
            return

        wrapped = _wrap_query(query, prefer_geo=prefer_geo)
        try:
            async for ev in sess.run_streaming(wrapped):
                kind = ev.get("event")
                if kind == "status":
                    src = ev.get("source", "?")
                    phase = ev.get("phase", "?")
                    label = f"{src}: {phase}"
                    if ev.get("error"):
                        label += f" (errore: {ev['error']})"
                    await task_updater.update_status(
                        state=TaskState.TASK_STATE_WORKING,
                        message=new_text_message(label),
                    )
                elif kind == "heartbeat":
                    secs = int(ev.get("elapsed_ms", 0) / 1000)
                    in_flight = ", ".join(ev.get("in_flight", [])) or "—"
                    await task_updater.update_status(
                        state=TaskState.TASK_STATE_WORKING,
                        message=new_text_message(f"heartbeat — {in_flight} ({secs}s)"),
                    )
                elif kind == "result":
                    text, resources = parse_agent_reply(ev.get("text", ""))
                    await fill_missing_content(resources)
                    try:
                        await upgrade_sdmx_resources(resources)
                    except Exception:
                        log.warning("upgrade_sdmx_resources failed", exc_info=True)
                    if settings.enable_osm_maps:
                        try:
                            await attach_maps(settings.osm_mcp_url, text, resources)
                        except Exception:
                            log.warning("attach_maps failed", exc_info=True)
                    if geo_only:
                        resources = [
                            r for r in resources
                            if (r.format or "").upper() in _GEO_FORMATS
                        ]
                    payload = {
                        "text": text,
                        "resources": [r.model_dump() for r in resources],
                    }
                    # Two artifact parts: a text/plain narrative (for clients
                    # that only understand text) + application/json with the
                    # structured resources list.
                    await task_updater.add_artifact(
                        parts=[
                            new_text_part(text=text, media_type="text/plain"),
                            new_text_part(
                                text=json.dumps(payload, ensure_ascii=False),
                                media_type="application/json",
                            ),
                        ],
                    )
                    await task_updater.update_status(
                        state=TaskState.TASK_STATE_COMPLETED,
                        message=new_text_message("Completed."),
                    )
                    return
                elif kind == "error":
                    await task_updater.update_status(
                        state=TaskState.TASK_STATE_FAILED,
                        message=new_text_message(ev.get("message", "stream error")),
                    )
                    return
        except Exception as exc:
            log.exception("A2A search execute failed")
            await task_updater.update_status(
                state=TaskState.TASK_STATE_FAILED,
                message=new_text_message(f"Errore interno: {exc}"),
            )

    async def _run_classify(
        self,
        context: RequestContext,
        task_updater: TaskUpdater,
        query_text: str,
    ) -> None:
        # classify_dataset expects a JSON payload. Accept it via either the
        # message text (plain JSON string) or via message.metadata.
        meta = getattr(context.message, "metadata", None) or {}
        payload: dict
        if isinstance(meta, dict) and meta.get("dataset_id"):
            payload = dict(meta)
        else:
            try:
                payload = json.loads(query_text)
            except Exception:
                await task_updater.update_status(
                    state=TaskState.TASK_STATE_FAILED,
                    message=new_text_message(
                        "classify_dataset richiede un JSON con source / dataset_id "
                        "/ dataset_name / taxonomy nel testo o nella metadata."
                    ),
                )
                return

        # Lazy import: classify wiring touches the DB session + Anthropic client
        # which are settings-dependent. Reuse the same `classify_dataset` helper
        # the FastAPI route does, but instantiate fresh DB + classifier here.
        from sqlalchemy.ext.asyncio import AsyncSession  # noqa: F401  (typing)

        from ..classify import classify_dataset
        from ..classify.anthropic_client import Classifier
        from ..db.session import get_session_factory

        settings = session_holder.settings
        if settings is None or not settings.anthropic_api_key:
            await task_updater.update_status(
                state=TaskState.TASK_STATE_FAILED,
                message=new_text_message("ANTHROPIC_API_KEY non configurata."),
            )
            return

        classifier = Classifier(
            api_key=settings.anthropic_api_key,
            model=settings.claude_classify_model,
        )
        try:
            factory = get_session_factory()
        except RuntimeError:
            await task_updater.update_status(
                state=TaskState.TASK_STATE_FAILED,
                message=new_text_message("DATABASE_URL non configurata."),
            )
            return

        async with factory() as session:
            try:
                result = await classify_dataset(
                    session,
                    classifier,
                    source=payload["source"],
                    dataset_id=payload["dataset_id"],
                    dataset_name=payload["dataset_name"],
                    dataset_description=payload.get("dataset_description"),
                    taxonomy=payload["taxonomy"],
                )
            except KeyError as exc:
                await task_updater.update_status(
                    state=TaskState.TASK_STATE_FAILED,
                    message=new_text_message(f"campo mancante: {exc}"),
                )
                return
            except Exception as exc:
                log.exception("A2A classify execute failed")
                await task_updater.update_status(
                    state=TaskState.TASK_STATE_FAILED,
                    message=new_text_message(f"Errore: {exc}"),
                )
                return

        out = {
            "source": result.source,
            "dataset_id": result.dataset_id,
            "scores": result.scores,
            "model": result.model,
            "cached": result.cached,
        }
        await task_updater.add_artifact(
            parts=[
                new_text_part(
                    text=json.dumps(out, ensure_ascii=False),
                    media_type="application/json",
                ),
            ],
        )
        await task_updater.update_status(
            state=TaskState.TASK_STATE_COMPLETED,
            message=new_text_message("Classified."),
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        # The underlying run_streaming has its own internal cancel path on
        # session shutdown; we treat A2A cancel as a no-op for now.
        raise NotImplementedError("cancel non ancora supportato")
