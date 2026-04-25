# Structured Chat Response Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat `reply: str` field in `POST /chat` with a structured JSON response containing a pure narrative `text` field and a `resources` list with name, URL, format, and optional content per resource.

**Architecture:** The LLM is instructed via `agent_instructions` to append a delimited JSON block (`<!--RESOURCES_JSON-->…<!--/RESOURCES_JSON-->`) after its narrative. The API layer strips and parses that block, then returns a typed `ChatResponse`. On any parse failure the endpoint degrades gracefully to `resources: []`.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, `re` (stdlib), pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `ckan-mcp-agent/src/ckan_agent/api.py` | Modify | New `Resource` + `ChatResponse` models; `parse_agent_reply()` helper; updated `chat()` endpoint |
| `ckan-mcp-agent/src/ckan_agent/config.py` | Modify | Append OUTPUT FORMAT RULE to `agent_instructions` |
| `ckan-mcp-agent/tests/test_api_parsing.py` | Create | Unit tests for `parse_agent_reply()` |

---

## Task 1: Unit tests for `parse_agent_reply()`

**Files:**
- Create: `ckan-mcp-agent/tests/test_api_parsing.py`

- [ ] **Step 1: Create the test file**

```python
"""Unit tests for parse_agent_reply() in ckan_agent.api."""

from __future__ import annotations

import pytest

from ckan_agent.api import Resource, parse_agent_reply


# ── happy path ────────────────────────────────────────────────────

def test_extracts_text_and_single_csv_resource():
    raw = (
        "Ho trovato il dataset sulle stazioni di ricarica.\n"
        "<!--RESOURCES_JSON-->\n"
        '[{"name":"stazioni.csv","url":"https://example.com/stazioni.csv",'
        '"format":"CSV","content":"id,lat\\n1,45.46"}]\n'
        "<!--/RESOURCES_JSON-->"
    )
    text, resources = parse_agent_reply(raw)
    assert text == "Ho trovato il dataset sulle stazioni di ricarica."
    assert len(resources) == 1
    r = resources[0]
    assert r.name == "stazioni.csv"
    assert r.url == "https://example.com/stazioni.csv"
    assert r.format == "CSV"
    assert r.content == "id,lat\n1,45.46"


def test_extracts_multiple_resources_mixed_formats():
    raw = (
        "Dataset trovato.\n"
        "<!--RESOURCES_JSON-->\n"
        '[{"name":"data.csv","url":"https://example.com/data.csv","format":"CSV","content":"a,b\\n1,2"},'
        '{"name":"map.shp","url":"https://example.com/map.shp","format":"SHP","content":null}]\n'
        "<!--/RESOURCES_JSON-->"
    )
    text, resources = parse_agent_reply(raw)
    assert text == "Dataset trovato."
    assert len(resources) == 2
    assert resources[0].content == "a,b\n1,2"
    assert resources[1].content is None
    assert resources[1].format == "SHP"


def test_text_has_no_trailing_whitespace():
    raw = (
        "Narrazione.\n\n"
        "<!--RESOURCES_JSON-->\n"
        "[]\n"
        "<!--/RESOURCES_JSON-->"
    )
    text, resources = parse_agent_reply(raw)
    assert text == "Narrazione."
    assert resources == []


# ── fallback / error cases ────────────────────────────────────────

def test_no_marker_block_returns_full_text_and_empty_resources():
    raw = "Nessun marcatore in questa risposta."
    text, resources = parse_agent_reply(raw)
    assert text == raw
    assert resources == []


def test_malformed_json_inside_marker_falls_back():
    raw = (
        "Testo.\n"
        "<!--RESOURCES_JSON-->\n"
        "questo non è json valido\n"
        "<!--/RESOURCES_JSON-->"
    )
    text, resources = parse_agent_reply(raw)
    assert text == raw
    assert resources == []


def test_empty_resources_array_is_valid():
    raw = (
        "Nessuna risorsa trovata.\n"
        "<!--RESOURCES_JSON-->\n"
        "[]\n"
        "<!--/RESOURCES_JSON-->"
    )
    text, resources = parse_agent_reply(raw)
    assert text == "Nessuna risorsa trovata."
    assert resources == []


def test_resource_model_fields():
    r = Resource(name="f.json", url="https://x.com/f.json", format="JSON", content='{"k":"v"}')
    assert r.name == "f.json"
    assert r.format == "JSON"
    assert r.content == '{"k":"v"}'


def test_resource_content_defaults_to_none():
    r = Resource(name="f.pdf", url="https://x.com/f.pdf", format="PDF")
    assert r.content is None
```

- [ ] **Step 2: Run tests — expect ImportError (symbols not yet defined)**

```bash
cd ckan-mcp-agent
python -m pytest tests/test_api_parsing.py -v 2>&1 | head -30
```

Expected output contains: `ImportError` or `cannot import name 'parse_agent_reply'`

---

## Task 2: New models and `parse_agent_reply()` in `api.py`

**Files:**
- Modify: `ckan-mcp-agent/src/ckan_agent/api.py`

- [ ] **Step 1: Replace the Pydantic models and add the parser**

Open `ckan-mcp-agent/src/ckan_agent/api.py`. Replace the existing model block (lines 19–25):

```python
class ChatRequest(BaseModel):
    query: str
    base_url: str | None = None  # optional override hint (agent passes it via tool args)


class ChatResponse(BaseModel):
    reply: str
```

with:

```python
import json
import re

_RESOURCES_RE = re.compile(
    r"<!--RESOURCES_JSON-->\s*(.*?)\s*<!--/RESOURCES_JSON-->",
    re.DOTALL,
)


class ChatRequest(BaseModel):
    query: str
    base_url: str | None = None


class Resource(BaseModel):
    name: str
    url: str
    format: str
    content: str | None = None


class ChatResponse(BaseModel):
    text: str
    resources: list[Resource]


def parse_agent_reply(raw: str) -> tuple[str, list[Resource]]:
    match = _RESOURCES_RE.search(raw)
    if not match:
        return raw, []
    json_block = match.group(1)
    try:
        items = json.loads(json_block)
        resources = [Resource(**item) for item in items]
    except Exception:
        return raw, []
    text = _RESOURCES_RE.sub("", raw).strip()
    return text, resources
```

The full updated imports section at the top of the file must include `import json` and `import re` — add them after `import logging`:

```python
"""FastAPI wrapper exposing the agent as a REST service."""

from __future__ import annotations

import json
import logging
import re
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .config import get_settings
from .factory import AgentSession
```

- [ ] **Step 2: Run the parsing tests — expect PASS**

```bash
cd ckan-mcp-agent
python -m pytest tests/test_api_parsing.py -v
```

Expected output:
```
tests/test_api_parsing.py::test_extracts_text_and_single_csv_resource PASSED
tests/test_api_parsing.py::test_extracts_multiple_resources_mixed_formats PASSED
tests/test_api_parsing.py::test_text_has_no_trailing_whitespace PASSED
tests/test_api_parsing.py::test_no_marker_block_returns_full_text_and_empty_resources PASSED
tests/test_api_parsing.py::test_malformed_json_inside_marker_falls_back PASSED
tests/test_api_parsing.py::test_empty_resources_array_is_valid PASSED
tests/test_api_parsing.py::test_resource_model_fields PASSED
tests/test_api_parsing.py::test_resource_content_defaults_to_none PASSED
8 passed
```

- [ ] **Step 3: Commit**

```bash
cd ckan-mcp-agent
git add src/ckan_agent/api.py tests/test_api_parsing.py
git commit -m "feat: add Resource model and parse_agent_reply() helper"
```

---

## Task 3: Update `chat()` endpoint to use new models

**Files:**
- Modify: `ckan-mcp-agent/src/ckan_agent/api.py` (endpoint only)

- [ ] **Step 1: Update the `chat()` endpoint**

Replace the existing `chat()` function body (currently lines 54–62):

```python
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if _session is None:
        raise HTTPException(status_code=503, detail="Agent session not initialised")
    query = req.query
    if req.base_url:
        query = f"[Target portal: {req.base_url}] {query}"
    reply = await _session.run(query)
    return ChatResponse(reply=reply)
```

with:

```python
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if _session is None:
        raise HTTPException(status_code=503, detail="Agent session not initialised")
    query = req.query
    if req.base_url:
        query = f"[Target portal: {req.base_url}] {query}"
    raw = await _session.run(query)
    text, resources = parse_agent_reply(raw)
    return ChatResponse(text=text, resources=resources)
```

- [ ] **Step 2: Run all existing tests to ensure nothing is broken**

```bash
cd ckan-mcp-agent
python -m pytest -v
```

Expected: all tests pass (including `tests/test_config.py`).

- [ ] **Step 3: Commit**

```bash
git add src/ckan_agent/api.py
git commit -m "feat: update /chat endpoint to return structured text + resources"
```

---

## Task 4: Update `agent_instructions` in `config.py`

**Files:**
- Modify: `ckan-mcp-agent/src/ckan_agent/config.py`

- [ ] **Step 1: Append OUTPUT FORMAT RULE to `agent_instructions`**

In `config.py`, find the `agent_instructions` field (currently ends with `"...download URL so the user can access the original file."`).

Replace the entire `agent_instructions` default value with:

```python
    agent_instructions: str = Field(
        default=(
            "You are an assistant specialised in querying CKAN open data portals. "
            "Use the provided CKAN MCP tools to answer the user's questions. "
            "IMPORTANT: When the user does not specify a portal, you MUST omit the base_url "
            "parameter from tool calls so the server uses its default portal "
            "(https://www.dati.gov.it/opendata). Never guess or substitute a different portal. "
            "Always cite the portal base URL, dataset names and resource IDs in your answers. "
            "Prefer concrete, verifiable facts over speculation.\n\n"
            "RESOURCE DOWNLOAD RULE:\n"
            "When a dataset has resources, inspect each resource format:\n"
            "- CSV, JSON, GeoJSON, TXT → call ckan_resource_download to download the file.\n"
            "- All other formats (PDF, XLSX, XLS, SHP, WMS, WFS, KML, ZIP, ODS, XML, etc.) → "
            "do NOT download.\n\n"
            "OUTPUT FORMAT RULE:\n"
            "After your narrative answer, append EXACTLY this block with no extra text after it:\n"
            "<!--RESOURCES_JSON-->\n"
            '[{"name":"<filename or resource name>","url":"<direct resource URL>",'
            '"format":"<UPPERCASE FORMAT>","content":"<file text or null>"}]\n'
            "<!--/RESOURCES_JSON-->\n"
            "Rules for the block:\n"
            "- The narrative text MUST NOT contain any resource URLs or file content.\n"
            "- Every resource found (any format) must appear in the JSON array.\n"
            "- For CSV, JSON, GeoJSON, TXT resources: set \"content\" to the full downloaded text "
            "with newlines escaped as \\n.\n"
            "- For all other formats: set \"content\" to null (JSON null, not the string 'null').\n"
            "- \"format\" must be the uppercase format string (e.g. \"CSV\", \"PDF\", \"SHP\").\n"
            "- The JSON array must be valid — do not truncate it."
        )
    )
```

- [ ] **Step 2: Run all tests**

```bash
cd ckan-mcp-agent
python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add src/ckan_agent/config.py
git commit -m "feat: add OUTPUT FORMAT RULE to agent_instructions for structured JSON output"
```

---

## Task 5: Smoke test end-to-end (manual)

> This task requires the full stack running locally (MCP server + agent API).

- [ ] **Step 1: Start the stack**

```bash
# terminal 1 — MCP server
cd ckan-mcp-server
python -m ckan_mcp.server   # or: uvicorn ckan_mcp.server:app

# terminal 2 — agent API
cd ckan-mcp-agent
ckan-agent-api
```

- [ ] **Step 2: Send the electric-vehicle charging station query**

```bash
curl -s -X POST http://localhost:8002/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"Cerca dataset sulle stazioni di ricarica per auto elettriche. Scarica e leggi i file CSV trovati, fornendo gli URL di tutte le risorse."}' \
  | python -m json.tool
```

Expected: response has `"text"` (narrative, no URLs) and `"resources"` array. Each CSV resource has `"content"` populated; non-downloadable formats have `"content": null`.

- [ ] **Step 3: Verify fallback with a query that returns no resources**

```bash
curl -s -X POST http://localhost:8002/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"Verifica che il portale dati.gov.it sia raggiungibile e mostrami versione."}' \
  | python -m json.tool
```

Expected: `"resources": []` and `"text"` contains the full narrative.

- [ ] **Step 4: Final commit if any adjustments were needed**

```bash
git add -p
git commit -m "fix: adjust agent instructions / parsing after smoke test"
```

---

## Self-Review

**Spec coverage:**
- ✅ `Resource` model with `name`, `url`, `format`, `content` — Task 2
- ✅ `ChatResponse` with `text` + `resources` — Task 2
- ✅ `parse_agent_reply()` with regex extraction and graceful fallback — Task 2
- ✅ `chat()` endpoint updated — Task 3
- ✅ `agent_instructions` updated with OUTPUT FORMAT RULE — Task 4
- ✅ Fallback: LLM omits marker → `resources: []`, `text` = full reply — Task 2 (tests cover this)
- ✅ Fallback: malformed JSON → same — Task 2 (test `test_malformed_json_inside_marker_falls_back`)
- ✅ `factory.py` and `main.py` untouched — confirmed (not in file map)
- ✅ MCP server untouched — confirmed

**Placeholder scan:** No TBD, no "implement later", no vague steps. All code blocks are complete.

**Type consistency:** `Resource` defined in Task 2, imported in test file Task 1 (`from ckan_agent.api import Resource, parse_agent_reply`). `parse_agent_reply` returns `tuple[str, list[Resource]]` — matches usage in Task 3 (`text, resources = parse_agent_reply(raw)`). `ChatResponse(text=text, resources=resources)` matches the model definition. All consistent.
