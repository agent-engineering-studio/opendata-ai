"""Tests for the synth aggregator: resource merging + narrative synthesis fallbacks.

We use a tiny in-memory stub for the synth Agent so we don't need a live LLM.
The aggregator is the boundary that has to stay stable: deterministic merge of
resources, dedup by URL preferring populated content, source tagging, robust
fallback when one branch is empty or errors.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import pytest

from orchestrator.parsing import Resource
from orchestrator.synth import build_aggregator

_MARKER_RE = re.compile(
    r"<!--RESOURCES_JSON-->\s*(.*?)\s*<!--/RESOURCES_JSON-->", re.DOTALL
)


# ───────────────────────── helpers ─────────────────────────


@dataclass
class _StubAgentResponse:
    text: str


class _StubAgent:
    """Records the last prompt and returns a canned text."""

    def __init__(self, canned: str = "narrativa sintetica unificata") -> None:
        self.canned = canned
        self.last_prompt: str | None = None

    async def run(self, prompt: str) -> _StubAgentResponse:
        self.last_prompt = prompt
        return _StubAgentResponse(text=self.canned)


class _FailingAgent:
    async def run(self, prompt: str) -> _StubAgentResponse:
        raise RuntimeError("synth backend exploded")


@dataclass
class _StubInnerResponse:
    text: str


@dataclass
class _StubResult:
    """Mimics agent_framework.orchestrations.AgentExecutorResponse just enough."""

    executor_id: str
    agent_response: _StubInnerResponse


def _result(executor_id: str, raw_text: str) -> _StubResult:
    return _StubResult(executor_id=executor_id, agent_response=_StubInnerResponse(text=raw_text))


def _ckan_reply(resources: list[dict[str, Any]]) -> str:
    return (
        "Su dati.gov.it ho trovato due dataset rilevanti.\n"
        "<!--RESOURCES_JSON-->\n"
        f"{json.dumps(resources)}\n"
        "<!--/RESOURCES_JSON-->"
    )


def _istat_reply(resources: list[dict[str, Any]]) -> str:
    return (
        "Dal dataflow POPRES1 ho estratto la popolazione residente.\n"
        "<!--RESOURCES_JSON-->\n"
        f"{json.dumps(resources)}\n"
        "<!--/RESOURCES_JSON-->"
    )


def _extract_block(final_text: str) -> list[dict[str, Any]]:
    match = _MARKER_RE.search(final_text)
    assert match is not None, f"no RESOURCES_JSON block in:\n{final_text}"
    return json.loads(match.group(1))


# ───────────────────────── tests ─────────────────────────


@pytest.mark.asyncio
async def test_happy_path_tags_and_dedupes_resources() -> None:
    """Both specialists return resources; merger tags each by source, dedupes URL."""
    synth = _StubAgent("Sintesi delle due fonti.")
    aggregate = build_aggregator(synth)  # type: ignore[arg-type]

    ckan_res = [
        {"name": "a.csv", "url": "https://dati.toscana.it/a.csv", "format": "CSV", "content": "h\n1"},
        {"name": "shared.csv", "url": "https://example.org/shared.csv", "format": "CSV", "content": None},
    ]
    istat_res = [
        {"name": "POPRES1.csv", "url": "https://esploradati.istat.it/POPRES1.csv", "format": "CSV", "content": "h\n2"},
        {"name": "shared.csv", "url": "https://example.org/shared.csv", "format": "CSV", "content": "real-content"},
    ]
    results = [_result("ckan", _ckan_reply(ckan_res)), _result("istat", _istat_reply(istat_res))]

    out = await aggregate(results)
    block = _extract_block(out.text)

    by_url = {r["url"]: r for r in block}
    assert len(block) == 3, f"expected 3 deduped resources, got {len(block)}: {block}"
    assert by_url["https://dati.toscana.it/a.csv"]["source"] == "ckan"
    assert by_url["https://esploradati.istat.it/POPRES1.csv"]["source"] == "istat"
    # Shared URL: the entry with non-null content wins (ISTAT's "real-content").
    assert by_url["https://example.org/shared.csv"]["content"] == "real-content"

    # Synth agent must have seen both sections.
    assert synth.last_prompt is not None
    assert "=== CKAN ===" in synth.last_prompt
    assert "=== ISTAT ===" in synth.last_prompt
    assert "Sintesi delle due fonti." in out.text


@pytest.mark.asyncio
async def test_missing_marker_falls_back_to_url_extraction() -> None:
    """If one branch omits the marker, URL fallback still picks up data resources."""
    synth = _StubAgent("OK.")
    aggregate = build_aggregator(synth)  # type: ignore[arg-type]

    ckan_raw = "Vedi qui: https://dati.gov.it/d.csv per i dati."  # no marker block
    istat_raw = _istat_reply(
        [{"name": "POPRES1.csv", "url": "https://esploradati.istat.it/x.csv", "format": "CSV", "content": None}]
    )

    out = await aggregate([_result("ckan", ckan_raw), _result("istat", istat_raw)])
    block = _extract_block(out.text)
    urls = {r["url"]: r["source"] for r in block}
    assert "https://dati.gov.it/d.csv" in urls
    assert urls["https://dati.gov.it/d.csv"] == "ckan"
    assert urls["https://esploradati.istat.it/x.csv"] == "istat"


@pytest.mark.asyncio
async def test_one_branch_returns_no_text() -> None:
    """If a branch yields nothing, the aggregator still emits a well-formed answer."""
    synth = _StubAgent("Solo ISTAT ha risposto.")
    aggregate = build_aggregator(synth)  # type: ignore[arg-type]

    istat_raw = _istat_reply([
        {"name": "x.csv", "url": "https://esploradati.istat.it/x.csv", "format": "CSV", "content": "v"}
    ])
    out = await aggregate([_result("ckan", ""), _result("istat", istat_raw)])

    block = _extract_block(out.text)
    assert len(block) == 1
    assert block[0]["source"] == "istat"
    assert "Solo ISTAT ha risposto." in out.text
    # The CKAN section should be marked empty in the synth prompt.
    assert "(nessun risultato)" in (synth.last_prompt or "")


@pytest.mark.asyncio
async def test_synth_agent_failure_falls_back_to_concatenated_narratives() -> None:
    """When the synth LLM call raises, we still produce a coherent output."""
    aggregate = build_aggregator(_FailingAgent())  # type: ignore[arg-type]

    out = await aggregate(
        [
            _result("ckan", _ckan_reply([])),
            _result(
                "istat",
                _istat_reply(
                    [{"name": "x", "url": "https://esploradati.istat.it/x.csv", "format": "CSV", "content": "v"}]
                ),
            ),
        ]
    )
    # Final text must still carry both narrative fragments.
    assert "dati.gov.it" in out.text
    assert "POPRES1" in out.text
    block = _extract_block(out.text)
    assert any(r["source"] == "istat" for r in block)


@pytest.mark.asyncio
async def test_resource_model_accepts_optional_source() -> None:
    """Sanity check on the shared Resource pydantic model used end-to-end."""
    r = Resource(name="a", url="https://example.com", format="CSV", content=None)
    assert r.source is None
    r2 = r.model_copy(update={"source": "ckan"})
    assert r2.source == "ckan"


@pytest.mark.asyncio
async def test_four_source_fan_in_tags_each_resource_correctly() -> None:
    """With CKAN + ISTAT + EUROSTAT + OECD enabled, every resource keeps its source tag."""
    synth = _StubAgent("Sintesi 4-source.")
    aggregate = build_aggregator(synth)  # type: ignore[arg-type]

    results = [
        _result(
            "ckan",
            _ckan_reply([
                {"name": "ck", "url": "https://dati.gov.it/a.csv", "format": "CSV", "content": None}
            ]),
        ),
        _result(
            "istat",
            _istat_reply([
                {"name": "it", "url": "https://esploradati.istat.it/p.csv", "format": "CSV", "content": None}
            ]),
        ),
        _result(
            "eurostat",
            "Eurostat ha trovato dati sul PIL UE.\n"
            "<!--RESOURCES_JSON-->\n"
            '[{"name": "eu", "url": "https://ec.europa.eu/eurostat/d.csv", "format": "CSV", "content": null}]\n'
            "<!--/RESOURCES_JSON-->",
        ),
        _result(
            "oecd",
            "L'OECD copre la stessa metrica per i paesi membri.\n"
            "<!--RESOURCES_JSON-->\n"
            '[{"name": "oe", "url": "https://sdmx.oecd.org/d.csv", "format": "CSV", "content": null}]\n'
            "<!--/RESOURCES_JSON-->",
        ),
    ]
    out = await aggregate(results)
    block = _extract_block(out.text)
    by_source = {r["source"]: r for r in block}
    assert set(by_source.keys()) == {"ckan", "istat", "eurostat", "oecd"}

    # The synth prompt must contain all four sections in canonical order.
    prompt = synth.last_prompt or ""
    for section in ("=== CKAN ===", "=== ISTAT ===", "=== EUROSTAT ===", "=== OECD ==="):
        assert section in prompt, f"missing {section} in synth prompt"


@pytest.mark.asyncio
async def test_eurostat_substring_does_not_get_tagged_as_istat() -> None:
    """Regression: 'eurostat' must not be matched by an over-eager 'istat' substring rule."""
    from orchestrator.synth import _normalise_source_tag

    assert _normalise_source_tag("eurostat") == "eurostat"
    assert _normalise_source_tag("EuroStat") == "eurostat"
    assert _normalise_source_tag("istat-agent") == "istat"
    assert _normalise_source_tag("oecd-agent") == "oecd"
    assert _normalise_source_tag("ckan-it") == "ckan"
