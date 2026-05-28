"""Smoke tests for the duplicated parser (parsing.parse_agent_reply).

Full coverage already lives in ckan-mcp-agent/tests/test_api_parsing.py;
this file just pins the two corner cases the synth aggregator depends on.
"""

from __future__ import annotations

import json

from opendata_backend.orchestrator.parsing import parse_agent_reply


def test_parses_marker_block_and_strips_narrative() -> None:
    raw = (
        "Risposta narrativa.\n"
        "<!--RESOURCES_JSON-->\n"
        '[{"name": "a", "url": "https://x/a.csv", "format": "CSV", "content": null}]\n'
        "<!--/RESOURCES_JSON-->"
    )
    text, resources = parse_agent_reply(raw)
    assert text == "Risposta narrativa."
    assert len(resources) == 1
    assert resources[0].url == "https://x/a.csv"
    assert resources[0].source is None


def test_malformed_json_in_marker_returns_empty_resources() -> None:
    raw = (
        "Testo.\n"
        "<!--RESOURCES_JSON-->\n"
        "{not valid json}\n"
        "<!--/RESOURCES_JSON-->"
    )
    text, resources = parse_agent_reply(raw)
    assert resources == []
    # On malformed JSON we keep the raw text intact so the synth can still use it.
    assert "Testo." in text


def test_wrapper_object_with_resources_key_is_unwrapped() -> None:
    payload = {"resources": [{"name": "a", "url": "https://x/a.csv", "format": "CSV", "content": None}]}
    raw = (
        "Testo.\n"
        "<!--RESOURCES_JSON-->\n"
        f"{json.dumps(payload)}\n"
        "<!--/RESOURCES_JSON-->"
    )
    _, resources = parse_agent_reply(raw)
    assert len(resources) == 1
    assert resources[0].url == "https://x/a.csv"
