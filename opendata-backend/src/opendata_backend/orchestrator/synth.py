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
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from agent_framework import Agent

from ..config import _EUROSTAT_BASE_URL, _ISTAT_BASE_URL, _OECD_BASE_URL
from .geo_filter import filter_resources
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
    # AgentExecutorResponse from agent_framework.orchestrations: if we recognise
    # the wrapper, commit to it — an empty .text means the agent produced no
    # output, not that we should fall through and stringify the wrapper itself.
    agent_resp = getattr(result, "agent_response", None)
    if agent_resp is not None:
        text = getattr(agent_resp, "text", None)
        if text is not None:
            return text
        messages = getattr(agent_resp, "messages", None)
        if messages:
            last = messages[-1]
            return getattr(last, "text", None) or ""
        return ""
    # Direct AgentResponse
    text = getattr(result, "text", None)
    if text is not None:
        return text
    messages = getattr(result, "messages", None)
    if messages:
        last = messages[-1]
        return getattr(last, "text", None) or ""
    return ""


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
      - {"source_url": ...} + source == "opencoesione" → JSON API citation (no content)
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

            # ── knowledge graph: kg_query ritorna `sources` (SourceReference
            # con doc_id/document_name/page_number) — provenienza documentale,
            # una citazione per documento+pagina.
            if source == "kg":
                captured.extend(_kg_resources_from_payload(payload))
                continue

            # ── web (marketing-territoriale, Pezzo 10): web_search ritorna
            # `results[]` (title/url/snippet/date), web_fetch una pagina con
            # `content`. Diventano citazioni esterne (format WEB) — il guardrail
            # marketing le tratta come `ispirazione_esterna`.
            if source == "web":
                captured.extend(_web_resources_from_payload(payload))
                continue

            # ── fonti "citation-style" (opencoesione / osm / ispra): i tool
            # includono `source_url`, l'URL risolvibile di quella risposta.
            # Sono citazioni (format JSON), mai file — catturate anche quando
            # l'LLM le omette dal suo blocco RESOURCES_JSON.
            if source in _CITATION_SOURCES:
                cit = _citation_resource_from_payload(payload, source)
                if cit is not None:
                    captured.append(cit)
                # query_local comparativi: ogni progetto dei comuni simili /
                # fermo ha il SUO url → una citazione PER PROGETTO, così le
                # idee possono linkare "cosa hanno fatto gli altri comuni".
                captured.extend(_project_citations_from_rows(payload))
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
                continue

            # ── ckan_package_search / ckan_package_show: real dataset resources ──
            # Small local models invent placeholder URLs (e.g. .../uuid/...) in
            # the RESOURCES_JSON; the search result carries the REAL urls/formats.
            if source == "ckan":
                captured.extend(_ckan_resources_from_payload(payload))

    if captured:
        log.info("captured %d tool-output resources from %s", len(captured), source)
    return captured


# Resource formats worth surfacing from a CKAN search (skip license/UNKNOWN noise).
_CKAN_KEEP_FORMATS = {
    "CSV", "JSON", "GEOJSON", "TOPOJSON", "SHP", "KML", "KMZ", "GPKG", "GML",
    "XLSX", "XLS", "XML", "TXT", "PDF", "ZIP", "WMS", "WFS", "RDF",
}
_MAX_CKAN_CAPTURED = 15

# Surface geographic-renderable formats first so the UI's /mappa page sees them
# even when a package also exposes a CSV/JSON variant the LLM happened to download.
_FORMAT_PRIORITY = {
    "GEOJSON": 0, "KML": 0, "KMZ": 0, "SHP": 0, "GPKG": 0, "TOPOJSON": 0, "GML": 1,
    "WMS": 2, "WFS": 2,
    "CSV": 3, "JSON": 3, "XLSX": 3, "XLS": 3, "TXT": 3, "XML": 3, "RDF": 3,
}


def _ckan_resources_from_payload(payload: dict[str, Any]) -> list[Resource]:
    """Extract real resources from a ckan_package_search / package_show result."""
    pkgs: list[dict[str, Any]]
    if isinstance(payload.get("results"), list):
        pkgs = [p for p in payload["results"] if isinstance(p, dict)]
    elif isinstance(payload.get("resources"), list):
        pkgs = [payload]
    else:
        return []

    out: list[Resource] = []
    seen: set[str] = set()
    for pkg in pkgs:
        title = pkg.get("title") or pkg.get("name") or ""
        # Sort each package's resources so geo formats come first; CSV/JSON last.
        # Within a priority bucket, preserve original order.
        raw_resources = [r for r in (pkg.get("resources") or []) if isinstance(r, dict)]
        ordered = sorted(
            enumerate(raw_resources),
            key=lambda ir: (
                _FORMAT_PRIORITY.get((ir[1].get("format") or "").upper().strip(), 9),
                ir[0],
            ),
        )
        for _, r in ordered:
            url = r.get("url")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            if _is_placeholder_url(url):
                continue
            key = url.strip().lower()
            if key in seen:
                continue
            fmt = (r.get("format") or "").upper().strip()
            if fmt and fmt not in _CKAN_KEEP_FORMATS:
                continue
            seen.add(key)
            name = r.get("name") or (f"{title} — {url.split('/')[-1]}" if title else url.split("/")[-1])
            out.append(
                Resource(name=name[:120], url=url, format=fmt or "UNKNOWN", source="ckan")
            )
            if len(out) >= _MAX_CKAN_CAPTURED:
                return out
    return out


#: Fonti i cui tool emettono citazioni API (`source_url`) invece di file.
_CITATION_SOURCES = ("opencoesione", "osm", "ispra")

#: Quanti progetti per risultato comparativo diventano citazioni nominate.
_MAX_PROJECT_CITATIONS = 10


def _project_citations_from_rows(payload: dict[str, Any]) -> list[Resource]:
    """Righe-progetto dei kind comparativi → citazioni nominate per progetto.

    `opencoesione_query_local` (similar_projects / stalled_projects) ritorna
    `rows.progetti[]` con `url` risolvibile per CLP: senza queste citazioni le
    idee del brainstorming non potrebbero linkare i progetti dei comuni simili
    (i guardrail scarterebbero URL mai raccolti).
    """
    rows = payload.get("rows")
    if not isinstance(rows, dict) or not isinstance(rows.get("progetti"), list):
        return []
    out: list[Resource] = []
    for proj in rows["progetti"][:_MAX_PROJECT_CITATIONS]:
        if not isinstance(proj, dict):
            continue
        url = proj.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            continue
        titolo = str(proj.get("titolo") or proj.get("clp") or "progetto")[:80]
        comune = proj.get("comune")
        name = f"OpenCoesione — {titolo}" + (f" ({comune})" if comune else "")
        out.append(Resource(name=name[:120], url=url, format="JSON", source="opencoesione"))
    return out


#: Quante hit di web_search diventano citazioni (tieni piccolo il contesto LLM).
_MAX_WEB_CITATIONS = 12


def _web_resources_from_payload(payload: dict[str, Any]) -> list[Resource]:
    """web_search / web_fetch → citazioni esterne (format WEB, source="web").

    web_search ritorna ``{results: [{title,url,snippet,date}]}``; web_fetch
    ritorna ``{url, content}``. Entrambi diventano risorse WEB taggate
    ``source="web"`` — l'evidenza che le cita risulta `ispirazione_esterna`
    (campo derivato su Evidenza) e il guardrail marketing richiede ALMENO una
    di queste accanto a una premessa locale (Pezzo 10).
    """
    out: list[Resource] = []
    results = payload.get("results")
    if isinstance(results, list):
        for r in results[:_MAX_WEB_CITATIONS]:
            if not isinstance(r, dict):
                continue
            url = r.get("url")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            snippet = str(r.get("snippet") or "").strip()
            date = str(r.get("date") or "").strip()
            descr = (snippet[:140] + (f" — {date}" if date else "")).strip() or None
            out.append(
                Resource(
                    name=str(r.get("title") or url)[:120],
                    url=url,
                    format="WEB",
                    source="web",
                    description=descr,
                )
            )
        return out
    # web_fetch: una singola pagina recuperata con contenuto.
    url = payload.get("url")
    content = payload.get("content")
    if (
        isinstance(url, str)
        and url.startswith(("http://", "https://"))
        and isinstance(content, str)
        and content.strip()
    ):
        name = url.rstrip("/").split("/")[-1].split("?")[0] or url
        out.append(
            Resource(
                name=name[:120],
                url=url,
                format="WEB",
                source="web",
                content=content[:_MAX_CAPTURED_CHARS],
                description="(pagina recuperata)",
            )
        )
    return out


def _kg_resources_from_payload(payload: dict[str, Any]) -> list[Resource]:
    """SourceReference del kg_query → citazioni documentali (doc + pagina).

    Locator: `{KG_UI_URL}/documents/{doc_id}` quando la UI del KG è
    configurata; altrimenti un riferimento sintetico `kg://…` comunque
    tracciabile a documento+pagina (spec 09).
    """
    import os

    refs = payload.get("sources")
    if not isinstance(refs, list):
        return []
    ui_base = (os.getenv("KG_UI_URL") or "").rstrip("/")
    namespace = payload.get("namespace") or payload.get("thread_id") or ""
    out: list[Resource] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        doc_id = ref.get("doc_id")
        if not doc_id:
            continue
        page = ref.get("page_number")
        total = ref.get("total_pages")
        if ui_base:
            url = f"{ui_base}/documents/{doc_id}"
        else:
            ns = f"{namespace}/" if namespace else ""
            url = f"kg://{ns}{doc_id}" + (f"#p={page}" if page is not None else "")
        descr = f"p.{(page or 0) + 1}/{total or '?'}"
        out.append(
            Resource(
                name=str(ref.get("document_name") or doc_id)[:120],
                url=url,
                format="DOC",
                source="kg",
                description=descr,
            )
        )
    return out


def _citation_resource_from_payload(payload: dict[str, Any], source: str) -> Resource | None:
    """Build the JSON API citation for a citation-style tool result.

    The tools of these sources return a `source_url` field (the resolvable URL
    of that exact response). The name is derived from the payload shape so the
    citation reads meaningfully in the UI. Lookup/infrastructure responses
    (territory resolution, comune autocomplete) are not evidence — skipped.
    """
    source_url = payload.get("source_url")
    if not isinstance(source_url, str) or not source_url.startswith(("http://", "https://")):
        return None
    if "found" in payload:  # opencoesione_resolve_territorio — not a citation
        return None

    if source == "opencoesione":
        if "spend_ratio" in payload:
            where = payload.get("territorio") or payload.get("slug") or ""
            name = f"OpenCoesione — capacità di spesa {where}".strip()
        elif "aggregati" in payload:
            ctx = payload.get("contesto") or {}
            name = f"OpenCoesione — aggregati territoriali {ctx.get('nome_territorio') or ''}".strip()
        elif "cod_locale_progetto" in payload:
            name = f"OpenCoesione — progetto {payload['cod_locale_progetto']}"
        elif "results" in payload:
            kind = "soggetti" if "/soggetti" in source_url else "progetti"
            name = f"OpenCoesione — ricerca {kind} ({payload.get('total', '?')} risultati)"
        else:
            name = "OpenCoesione — risposta API"
    elif source == "osm":
        if "candidates" in payload:  # osm_list_zones — lookup, not evidence
            return None
        name = f"OpenStreetMap — {payload.get('name') or 'entità'}"
    elif source == "ispra":
        nome = payload.get("nome") or payload.get("cod_comune") or ""
        name = f"ISPRA IdroGEO — indicatori di rischio {nome}".strip()
    else:  # pragma: no cover — _CITATION_SOURCES is closed
        name = f"{source.upper()} — risposta API"
    return Resource(name=name[:120], url=source_url, format="JSON", source=source)  # type: ignore[arg-type]


_PLACEHOLDER_SEGMENTS = ("uuid", "example", "your-", "path", "<", "{", "...")

# A UUID-shaped path segment (8-4-4-4-12) …
_UUID_SHAPE_RE = re.compile(r"^[0-9a-z]{8}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{12}$")
# … that is actually valid hex. Real CKAN resource ids are hex UUIDs; a model
# that invents an id writes non-hex junk (e.g. ...-ghij-klmnopqrstuv) or a
# sequential 12345678-... — both are hallucinations that 404.
_HEX_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _is_placeholder_url(url: str) -> bool:
    """Detect templated/hallucinated URLs (e.g. .../dataset/uuid/resource/uuid/x)."""
    low = url.lower()
    if "<" in low or "{" in low or "..." in low or "example.com" in low:
        return True
    # The literal path segment "uuid" is a placeholder (real CKAN ids are 36-char hex).
    segs = low.split("/")
    if "uuid" in segs:
        return True
    # Fabricated resource id: UUID-shaped but not valid hex, or the giveaway
    # sequential 12345678-… that weak models love to emit.
    for seg in segs:
        if _UUID_SHAPE_RE.match(seg) and (
            not _HEX_UUID_RE.match(seg) or seg.startswith("12345678-")
        ):
            return True
    return False


# Fill-in template placeholders a weak local model leaks INSTEAD of real numbers,
# e.g. "un tasso di spesa del [Spend Ratio]% con [Numero di Progetti Completati]
# progetti … per [Importo Totale €]". A bracketed span carrying a letter never
# appears in a legitimate narrative here (citations live in the RESOURCES_JSON
# block, not inline), so we treat it as template leakage and drop the sentence —
# presenting blanks as if they were facts is worse than omitting the claim.
_PLACEHOLDER_TOKEN_RE = re.compile(r"\[[^\]\n]*[A-Za-z][^\]\n]*\]")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _strip_placeholder_sentences(text: str) -> str:
    """Drop sentences that carry an unfilled `[...]` template placeholder.

    Returns the text unchanged when no placeholder is present. When stripping
    removes everything, returns "" so the caller's empty-narrative fallback
    produces an honest message rather than echoing the blanks.
    """
    if not text or not _PLACEHOLDER_TOKEN_RE.search(text):
        return text
    sentences = _SENTENCE_SPLIT_RE.split(text)
    kept = [s for s in sentences if not _PLACEHOLDER_TOKEN_RE.search(s)]
    return " ".join(s.strip() for s in kept).strip()


def _normalise_source_tag(executor_id: str) -> str | None:
    """Map the participant's executor_id to a clean source tag.

    Recognised tags: 'ckan', 'ods', 'socrata', 'istat', 'eurostat', 'oecd',
    'opencoesione'. Match is substring-based against a lowercased executor_id so
    renames at the Settings level (e.g. `ckan_agent_name="ckan-it"`) keep working.
    """
    lower = executor_id.lower()
    for tag in ("opencoesione", "eurostat", "oecd", "istat", "socrata", "ckan", "ods", "ispra", "osm", "web", "kg"):
        # longest-first: eurostat before istat so a literal "eurostat" doesn't
        # get matched as istat; opencoesione first for the same reason. "kg"
        # è ultimo perché cortissimo (matcherebbe dentro nomi più lunghi).
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


_SYNTH_SOURCE_ORDER = (
    "ckan", "ods", "socrata", "istat", "eurostat", "oecd", "opencoesione", "osm", "ispra", "kg", "web"
)


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
    user_query: str | None = None,
) -> Callable[[list[Any]], Awaitable[_SynthOutput]]:
    """Return an async aggregator suitable for ConcurrentBuilder.with_aggregator.

    `user_query` enables the deterministic geographic post-filter — when the
    user names a specific Italian comune, resources that point at a different
    comune are dropped before the JSON block is serialised. Pass None to skip
    the filter entirely (tests, callers without a query in hand).
    """

    async def aggregate(
        results: list[Any],
        emit: Callable[[dict[str, Any]], None] | None = None,
    ) -> _SynthOutput:
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
                # Still record an empty narrative so the synth prompt renders
                # the section as "(nessun risultato)" instead of dropping it.
                if source:
                    narratives_by_source[source] = ""
                else:
                    narratives_by_source.setdefault(exec_id, "")
                continue
            narrative, resources = parse_agent_reply(raw_text)
            # Drop sentences with unfilled `[...]` template placeholders (a weak
            # model leaks "[Spend Ratio]%" etc. instead of real numbers).
            stripped = _strip_placeholder_sentences(narrative)
            if stripped != narrative:
                log.warning("aggregator: stripped template placeholders from %s narrative", exec_id)
                narrative = stripped
            # Drop hallucinated placeholder URLs (small models emit .../uuid/... links).
            resources = [r for r in resources if not _is_placeholder_url(r.url)]
            # Deterministically capture tool outputs (real CKAN resource URLs, CSV
            # observations, downloaded files) so data surfaces even when the LLM
            # omits or fabricates it in the block.
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
        if user_query:
            merged_resources = filter_resources(merged_resources, user_query)

        # Ask the synth agent to merge the narratives. With `emit`, stream the
        # tokens as `thinking` events so the client sees the answer being
        # written instead of a frozen wait (mirrors run_programma_streaming).
        synth_prompt = _build_synth_prompt(narratives_by_source)
        try:
            if emit is not None:
                chunks: list[str] = []
                async for update in synth_agent.run(synth_prompt, stream=True):
                    delta = getattr(update, "text", None)
                    if delta:
                        chunks.append(delta)
                        emit({"event": "thinking", "source": "synth", "delta": delta})
                unified_narrative = "".join(chunks).strip()
            else:
                synth_result = await synth_agent.run(synth_prompt)
                unified_narrative = (
                    getattr(synth_result, "text", None) or str(synth_result)
                ).strip()
        except Exception:
            log.exception("synth agent failed; falling back to concatenated narratives")
            unified_narrative = "\n\n".join(
                n for n in narratives_by_source.values() if n
            ).strip()

        # Final safety net: even with cleaned inputs the synth model can emit its
        # own fill-in template — never let "[Spend Ratio]%" reach the user.
        deplaceheld = _strip_placeholder_sentences(unified_narrative)
        if deplaceheld != unified_narrative:
            log.warning("aggregator: stripped template placeholders from synth output")
            unified_narrative = deplaceheld

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
