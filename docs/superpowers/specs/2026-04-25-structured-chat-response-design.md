# Structured Chat Response Design

**Date:** 2026-04-25  
**Status:** Approved  
**Scope:** `ckan-mcp-agent` only — MCP server untouched

---

## Problem

The `POST /chat` endpoint currently returns a single `reply: str` field containing markdown text. When the agent finds CSV resources and downloads them, both the narrative description and the file content (plus URLs) are flattened into one unstructured string. Clients cannot reliably extract resource URLs or file content programmatically.

## Goal

Return a structured JSON response that separates:
- **`text`** — pure narrative (no URLs, no file content)
- **`resources`** — one entry per resource found, with name, URL, format, and content (only for downloadable formats)

---

## Response Contract

```python
class Resource(BaseModel):
    name: str
    url: str
    format: str                  # e.g. "CSV", "JSON", "SHP", "PDF"
    content: str | None = None   # populated only for CSV / JSON / GeoJSON / TXT
```

```python
class ChatResponse(BaseModel):
    text: str                    # narrative only, no URLs or file content
    resources: list[Resource]    # empty list when no resources found
```

### Example response

```json
{
  "text": "Ho trovato il dataset 'Stazioni di ricarica auto elettriche' pubblicato dal Comune di Milano (CC BY 4.0). Il dataset copre le stazioni presenti sul territorio comunale.",
  "resources": [
    {
      "name": "ds642_stazioni_ricarica.csv",
      "url": "https://dati.comune.milano.it/.../stazioni_ricarica.csv",
      "format": "CSV",
      "content": "id,lat,lon,tipo_presa\n1,45.46,9.19,CCS\n..."
    },
    {
      "name": "Mappa stazioni",
      "url": "https://dati.comune.milano.it/.../stazioni.shp",
      "format": "SHP",
      "content": null
    }
  ]
}
```

---

## Approach: Prompt Engineering + Post-hoc Parsing

The agent is instructed to append a structured JSON block at the end of every reply, delimited by HTML-comment markers. The API layer extracts and parses this block, then builds the structured response.

### Why this approach

- Works with all configured providers (Ollama, Azure Foundry, Claude)
- No changes to the MCP server or `factory.py`
- Graceful fallback: if the LLM does not produce the marker block, `resources` is `[]` and `text` contains the full raw reply — the response is always valid

---

## Files Modified

### 1. `ckan-mcp-agent/src/ckan_agent/config.py`

Append to `agent_instructions` a new section:

```
OUTPUT FORMAT RULE:
After your narrative answer, append exactly this block (no extra text after it):
<!--RESOURCES_JSON-->
[{"name":"<filename>","url":"<url>","format":"<FORMAT>","content":"<file content or null>"}]
<!--/RESOURCES_JSON-->
Rules:
- The narrative text MUST NOT contain any resource URLs or file content.
- Every resource found (any format) must appear in the JSON array.
- For CSV, JSON, GeoJSON, TXT resources: set "content" to the full downloaded text.
- For all other formats (PDF, SHP, XLSX, WMS, KML, ZIP, etc.): set "content" to null.
- "format" must be the uppercase format string (e.g. "CSV", "PDF", "SHP").
- The JSON must be valid — escape newlines in content as \n.
```

### 2. `ckan-mcp-agent/src/ckan_agent/api.py`

- Replace `ChatResponse(reply: str)` with `Resource` + `ChatResponse(text, resources)` models
- Add `parse_agent_reply(raw: str) -> tuple[str, list[Resource]]` helper:
  - Regex-extract content between `<!--RESOURCES_JSON-->` and `<!--/RESOURCES_JSON-->`
  - `json.loads()` the extracted block → list of `Resource`
  - Strip the marker block from the raw string → `text`
  - On any parse failure → return `(raw, [])`
- Update `chat()` endpoint to call `parse_agent_reply()` and return `ChatResponse(text=..., resources=...)`

### 3. `requests/agent-chat.http`

No changes needed. The request contract (`query`, optional `base_url`) is unchanged.

---

## Out of Scope

- `factory.py` — `AgentSession.run()` continues returning a plain string
- `main.py` — interactive CLI is not affected
- `ckan-mcp-server/` — MCP server is untouched

---

## Error Handling

| Situation | Behaviour |
|-----------|-----------|
| LLM omits marker block | `resources: []`, `text` = full raw reply |
| JSON inside marker is malformed | `resources: []`, `text` = full raw reply |
| `AgentSession` not initialised | HTTP 503 (unchanged) |
