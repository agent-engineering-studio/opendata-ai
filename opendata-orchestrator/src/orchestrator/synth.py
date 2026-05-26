"""Synthesizer aggregator used by ConcurrentBuilder.

Receives the list of per-participant `AgentExecutorResponse`s, parses each one
through `parse_agent_reply`, deterministically merges + deduplicates resources,
then asks an LLM-backed `synth_agent` to merge the two narratives into one.

Output: a final stringified message in the canonical
`<unified narrative>\n<!--RESOURCES_JSON-->\n<json>\n<!--/RESOURCES_JSON-->`
shape, returned as an `AgentResponse`-shaped object so the workflow's
`events.get_outputs()` keeps working.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from agent_framework import Agent

from .config import _EUROSTAT_BASE_URL, _ISTAT_BASE_URL, _OECD_BASE_URL
from .parsing import Resource, parse_agent_reply

log = logging.getLogger("orchestrator.synth")

# Cap embedded CSV content captured from tool results (ISTAT full cubes reach tens of MB).
_MAX_CAPTURED_CHARS = 200_000

# Map a source tag to the SDMX endpoint base, used to build a clickable URL for
# CSV observations captured from `istat_get_data` (whose result carries only a path).
_SOURCE_BASE_URL = {
    "istat": _ISTAT_BASE_URL,
    "eurostat": _EUROSTAT_BASE_URL,
    "oecd": _OECD_BASE_URL,
}


@dataclass
class _SynthOutput:
    """Minimal AgentResponse-shaped object the workflow can read .text from."""
    text: str


def _extract_text_from_result(result: Any) -> str:
    """Best-effort extraction of the final assistant text from an executor result."""
    if result is None:
        return ""
    if isinstance(result, BaseException):
        return ""
    # AgentExecutorResponse from agent_framework.orchestrations
    agent_resp = getattr(result, "agent_response", None)
    if agent_resp is not None:
        text = getattr(agent_resp, "text", None)
        if text:
            return text
        messages = getattr(agent_resp, "messages", None)
        if messages:
            last = messages[-1]
            text = getattr(last, "text", None)
            if text:
                return text
    # Direct AgentResponse
    text = getattr(result, "text", None)
    if text:
        return text
    messages = getattr(result, "messages", None)
    if messages:
        last = messages[-1]
        text = getattr(last, "text", None)
        if text:
            return text
    return str(result)


def _executor_id(result: Any) -> str:
    return (
        getattr(result, "executor_id", None)
        or getattr(result, "agent_id", None)
        or getattr(result, "name", None)
        or "unknown"
    )


def _coerce_tool_result(raw: Any) -> dict[str, Any] | None:
    """Normalise a function_result `.result` value into a dict, best-effort.

    Handles: dict directly, JSON string, or an MCP content list whose text parts
    contain JSON. Returns None if nothing dict-like can be recovered.
    """
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except (ValueError, TypeError):
            return None
    # MCP content list (e.g. [{"type":"text","text":"{...}"}]) or objects with .text
    if isinstance(raw, (list, tuple)):
        for item in raw:
            text = item.get("text") if isinstance(item, dict) else getattr(item, "text", None)
            if isinstance(text, str):
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        return parsed
                except (ValueError, TypeError):
                    continue
    return None


def _iter_messages(result: Any) -> list[Any]:
    conv = getattr(result, "full_conversation", None)
    if conv:
        return list(conv)
    agent_resp = getattr(result, "agent_response", None)
    msgs = getattr(agent_resp, "messages", None) if agent_resp is not None else None
    return list(msgs) if msgs else []


def _capture_tool_resources(result: Any, source: str | None) -> list[Resource]:
    """Deterministically turn MCP tool results into resources with content.

    Scans the participant's message history for `function_result` contents and,
    based on the result *shape* (not a fragile name match), builds resources:
      - {"csv": ...}                 → istat_get_data    → CSV resource (content)
      - {"content": ..., "url": ...} → ckan_resource_download → resource (content)
    """
    captured: list[Resource] = []
    base = _SOURCE_BASE_URL.get(source or "", None)

    for msg in _iter_messages(result):
        for content in (getattr(msg, "contents", None) or []):
            if getattr(content, "type", None) != "function_result":
                continue
            payload = _coerce_tool_result(getattr(content, "result", None))
            if not payload:
                continue

            # ── istat_get_data: SDMX-CSV observations ──
            csv_text = payload.get("csv")
            if isinstance(csv_text, str) and csv_text.strip():
                # ISTAT full-cube CSVs can be tens of MB — cap before embedding.
                if len(csv_text) > _MAX_CAPTURED_CHARS:
                    csv_text = (
                        csv_text[:_MAX_CAPTURED_CHARS]
                        + f"\n\n[…troncato a {_MAX_CAPTURED_CHARS} caratteri; "
                        "restringi con key/start_period/last_n per il dato completo]"
                    )
                path = payload.get("path") or "data"
                params = payload.get("params") or {}
                qs = "&".join(f"{k}={v}" for k, v in params.items())
                url = f"{base.rstrip('/')}/{path}" if base else str(path)
                if qs:
                    url = f"{url}?{qs}"
                dataflow = str(path).split("/")[1] if "/" in str(path) else str(path)
                captured.append(
                    Resource(
                        name=f"{(source or 'sdmx').upper()} {dataflow} (osservazioni CSV)",
                        url=url,
                        format="CSV",
                        content=csv_text,
                        source=source,  # type: ignore[arg-type]
                    )
                )
                continue

            # ── ckan_resource_download: file already fetched server-side ──
            dl_content = payload.get("content")
            dl_url = payload.get("url")
            if isinstance(dl_content, str) and dl_content.strip() and isinstance(dl_url, str):
                ctype = (payload.get("content_type") or "").lower()
                fmt = "CSV" if "csv" in ctype else (
                    "JSON" if "json" in ctype else (
                        "XML" if "xml" in ctype else "TXT"
                    )
                )
                name = dl_url.rstrip("/").split("/")[-1].split("?")[0] or dl_url
                captured.append(
                    Resource(name=name, url=dl_url, format=fmt, content=dl_content, source=source)  # type: ignore[arg-type]
                )

    if captured:
        log.info("captured %d tool-output resources from %s", len(captured), source)
    return captured


def _normalise_source_tag(executor_id: str) -> str | None:
    """Map the participant's executor_id to a clean source tag.

    Recognised tags: 'ckan', 'istat', 'eurostat', 'oecd'. Match is substring-based
    against a lowercased executor_id so renames at the Settings level (e.g.
    `ckan_agent_name="ckan-it"`) keep working.
    """
    lower = executor_id.lower()
    for tag in ("eurostat", "oecd", "istat", "ckan"):
        # eurostat before istat so a literal "eurostat" doesn't get matched as istat
        if tag in lower:
            return tag
    return None


def _merge_resources(
    parts: list[tuple[str | None, list[Resource]]],
) -> list[Resource]:
    """Tag each resource with its source and dedupe by URL.

    On URL collision, the entry with non-null `content` wins; otherwise the
    first occurrence is kept.
    """
    by_url: dict[str, Resource] = {}
    for source, resources in parts:
        for r in resources:
            tagged = r.model_copy(update={"source": source}) if source else r
            url_key = tagged.url.strip().lower()
            existing = by_url.get(url_key)
            if existing is None:
                by_url[url_key] = tagged
                continue
            if existing.content is None and tagged.content is not None:
                by_url[url_key] = tagged
    return list(by_url.values())


def _resources_to_json_block(resources: list[Resource]) -> str:
    payload = [r.model_dump(exclude_none=False) for r in resources]
    return json.dumps(payload, ensure_ascii=False)


_SYNTH_SOURCE_ORDER = ("ckan", "istat", "eurostat", "oecd")


def _build_synth_prompt(narratives_by_source: dict[str, str]) -> str:
    parts: list[str] = []
    for source in _SYNTH_SOURCE_ORDER:
        if source not in narratives_by_source:
            continue
        body = narratives_by_source[source].strip() or "(nessun risultato)"
        parts.append(f"=== {source.upper()} ===\n{body}")
    # Any unrecognised sources still get a section (helps debugging if someone
    # renames an agent without updating _normalise_source_tag).
    for source, body in narratives_by_source.items():
        if source in _SYNTH_SOURCE_ORDER:
            continue
        parts.append(f"=== {source.upper()} ===\n{body.strip() or '(nessun risultato)'}")
    return "\n\n".join(parts) + "\n"


def build_aggregator(
    synth_agent: Agent,
) -> Callable[[list[Any]], Awaitable[_SynthOutput]]:
    """Return an async aggregator suitable for ConcurrentBuilder.with_aggregator."""

    async def aggregate(results: list[Any]) -> _SynthOutput:
        log.info("Aggregator received %d participant results", len(results))
        parts: list[tuple[str | None, list[Resource]]] = []
        narratives_by_source: dict[str, str] = {}

        for result in results:
            exec_id = _executor_id(result)
            source = _normalise_source_tag(exec_id)
            raw_text = _extract_text_from_result(result)
            if not raw_text:
                log.warning("aggregator: participant %s produced no text", exec_id)
                parts.append((source, []))
                continue
            narrative, resources = parse_agent_reply(raw_text)
            # Deterministically capture tool outputs (CSV observations, downloaded
            # files) so the data surfaces even when the LLM omits it from the block.
            resources = resources + _capture_tool_resources(result, source)
            parts.append((source, resources))
            if source:
                narratives_by_source[source] = narrative
            else:
                narratives_by_source.setdefault(exec_id, narrative)

        merged_resources = _merge_resources(parts)
        log.info(
            "aggregator: merged %d resources from %d sources",
            len(merged_resources), len(parts),
        )

        # Ask the synth agent to merge the narratives.
        synth_prompt = _build_synth_prompt(narratives_by_source)
        try:
            synth_result = await synth_agent.run(synth_prompt)
            unified_narrative = (
                getattr(synth_result, "text", None) or str(synth_result)
            ).strip()
        except Exception:
            log.exception("synth agent failed; falling back to concatenated narratives")
            unified_narrative = "\n\n".join(
                n for n in narratives_by_source.values() if n
            ).strip()

        if not unified_narrative:
            unified_narrative = (
                "Nessuna risposta utile dai due specialisti per questa query."
            )

        final = (
            f"{unified_narrative}\n"
            f"<!--RESOURCES_JSON-->\n"
            f"{_resources_to_json_block(merged_resources)}\n"
            f"<!--/RESOURCES_JSON-->"
        )
        return _SynthOutput(text=final)

    return aggregate
