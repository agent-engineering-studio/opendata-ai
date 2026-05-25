# Resource Preview Inline + Markdown Rendering — Design

**Date:** 2026-05-25
**Status:** Approved (ready for implementation plan)
**Scope:** `ckan-mcp-ui` (UI) + `ckan-mcp-agent` (backend, minimal)

## Problem

Today, when the agent returns a dataset answer, the chat UI shows:

1. The agent's reply as plain paragraphs split on blank lines, with no markdown formatting (no headings, lists, **bold**, tables, links rendered as text).
2. A list of resources where each card shows only `[FORMAT] name → Apri`. The downloaded `Resource.content` field (populated by the backend for CSV/JSON/GeoJSON/TXT) is **ignored**.

Concrete user impact: asking *"Mostrami i dettagli del dataset 2908fe96-…"* returns a list of CSV/PDF links but the user cannot see the CSV table in the chat — they must click "Apri", leave the chat, and look at the raw file in a new tab. Markdown structure produced by the LLM (headings, bullet lists, **bold**) is flattened.

## Goals

- Render the assistant reply as proper GitHub-flavored markdown (headings, lists, code, tables, links, emphasis).
- Show an inline preview of downloaded resource content, format-aware:
  - **CSV** → parsed virtualized table
  - **JSON / GeoJSON** → pretty-printed JSON with light syntax coloring
  - **XML / RDF / KML / WMS / WFS / WCS capabilities** → pretty-printed XML code block
  - **TXT** → monospace text
  - **Binary** (PDF / XLSX / ZIP / SHP / …) → link only, no preview
- Extend the backend so XML / RDF / KML / WMS / WFS / WCS resources are downloaded too (today only CSV/JSON/GeoJSON/TXT are).

## Non-goals

- Charts, maps, or any data visualization beyond a flat table.
- Editing / filtering / sorting CSV rows in the UI.
- A modal or full-screen viewer.
- Server-side rendering of CSV→HTML.
- Adding a UI test framework.

## Architecture

Two independent, small changes shipped as two commits:

### Backend — single-line change

`ckan-mcp-agent/src/ckan_agent/api.py:44` — extend `_DOWNLOADABLE_FORMATS`:

```python
_DOWNLOADABLE_FORMATS = frozenset({
    "CSV", "JSON", "GEOJSON", "TXT",
    "XML", "RDF", "KML", "WMS", "WFS", "WCS",
})
```

The existing `_fetch_text` pipeline (200 KB cap, response-encoding decode, truncation notice) already handles these formats. No other backend change. The `Resource{name,url,format,content}` shape is unchanged.

### UI — new preview components + markdown renderer

All routing of the preview renderer happens client-side based on `resource.format` (uppercase). The backend stays format-agnostic.

```
ckan-mcp-ui/components/
  ├── Message.tsx                # MODIFIED: assistant text → AssistantMarkdown
  ├── ResourceCard.tsx           # MODIFIED: adds "Anteprima" toggle
  ├── AssistantMarkdown.tsx      # NEW: react-markdown + remark-gfm wrapper
  └── preview/
      ├── ResourcePreview.tsx    # NEW: dispatcher by format
      ├── CsvTablePreview.tsx    # NEW: papaparse + react-virtual
      ├── JsonPreview.tsx        # NEW: JSON.parse + pretty-print + CSS coloring
      ├── XmlPreview.tsx         # NEW: DOMParser + prettyPrintXml()
      └── TextPreview.tsx        # NEW: <pre whitespace-pre-wrap>; also fallback
```

## Components

### `AssistantMarkdown.tsx` (new)

Wraps `<ReactMarkdown remarkPlugins={[remarkGfm]} components={...}>` with Tailwind class overrides on every block element:

| Element | Tailwind classes |
|---|---|
| `h1`/`h2`/`h3` | `font-semibold text-slate-900 mt-3 mb-1 text-{lg,base,sm}` |
| `p` | `leading-relaxed` |
| `ul`/`ol` | `list-{disc,decimal} pl-5 space-y-1` |
| `li` | (inherits) |
| `code` (inline) | `rounded bg-slate-100 px-1 py-0.5 font-mono text-[0.85em]` |
| `pre` / `code` (block) | `rounded-md bg-slate-900 text-slate-100 p-3 overflow-auto text-sm font-mono` |
| `blockquote` | `border-l-4 border-slate-300 pl-3 text-slate-600 italic` |
| `table` / `th` / `td` | `border-collapse text-sm`, `border border-slate-200 px-2 py-1` |
| `a` | `text-blue-700 hover:text-blue-900 underline`, `target="_blank" rel="noopener noreferrer"` |

User and error messages remain plain `<p>` — they are never markdown.

### `ResourceCard.tsx` (modified)

Adds local state `const [expanded, setExpanded] = useState(false)`.

The current row (badge + name + "→ Apri") stays unchanged. Underneath, when `content` is available **and** `format` is in the textual set, a small toolbar appears:

```
[▸ Mostra anteprima]   ~12 KB · 245 righe
```

Clicking expands `<ResourcePreview format={...} content={...}/>` inline; clicking again collapses.

If `content === null` or the format is binary, no toolbar — card behavior identical to today.

### `ResourcePreview.tsx` (new — dispatcher)

```ts
type Props = { format: string; content: string };

const TEXTUAL_FORMATS = new Set([
  "CSV", "JSON", "GEOJSON", "TXT",
  "XML", "RDF", "KML", "WMS", "WFS", "WCS",
]);

export function ResourcePreview({ format, content }: Props) {
  const f = format.toUpperCase();
  if (!TEXTUAL_FORMATS.has(f)) return null;
  if (f === "CSV") return <CsvTablePreview content={content} />;
  if (f === "JSON" || f === "GEOJSON") return <JsonPreview content={content} />;
  if (["XML","RDF","KML","WMS","WFS","WCS"].includes(f)) return <XmlPreview content={content} />;
  return <TextPreview content={content} />;
}
```

The dispatcher also exposes a helper `isPreviewable(format, content)` reused by `ResourceCard` to decide whether to render the toggle.

### `CsvTablePreview.tsx` (new)

- Parses with `Papa.parse(content, { header: true, delimiter: "", skipEmptyLines: true, dynamicTyping: false })` — empty `delimiter` enables PapaParse's auto-detect (`;`, `,`, `\t`, `|`).
- If `result.errors.length > 0`, render a yellow banner: *"Formato CSV non standard — alcune righe potrebbero essere errate"* and continue with what was parsed.
- Renders a virtualized table using `useVirtualizer` from `@tanstack/react-virtual`:
  - Container: `max-h-96 overflow-auto border rounded`
  - `<thead>` sticky (`sticky top-0 bg-slate-50`)
  - Each cell: `truncate max-w-[20ch]` + `title={cellValue}` for tooltip on overflow
  - Estimated row size 32px
- Header of the preview shows `{rows.length} righe · {fields.length} colonne`.

### `JsonPreview.tsx` (new)

```ts
try {
  const obj = JSON.parse(content);
  const pretty = JSON.stringify(obj, null, 2);
  return <pre className="...">{tokenize(pretty)}</pre>;
} catch {
  return <TextPreview content={content} />;
}
```

`tokenize` is a small inline function (~30 lines) that runs a regex over the pretty-printed JSON and wraps matches in `<span class="json-{string|number|boolean|null|key}">`. CSS classes defined in `globals.css`. No external syntax-highlighter dependency.

### `XmlPreview.tsx` (new)

```ts
const doc = new DOMParser().parseFromString(content, "application/xml");
const errorNode = doc.querySelector("parsererror");
if (errorNode) return <TextPreview content={content} />;
return <pre className="...">{prettyPrintXml(doc.documentElement)}</pre>;
```

`prettyPrintXml` walks the DOM and indents by depth (~40 lines, no dependency). Output goes in a dark `<pre>` block like markdown code blocks.

### `TextPreview.tsx` (new)

```tsx
<pre className="whitespace-pre-wrap break-words font-mono text-xs bg-slate-50 p-3 rounded max-h-96 overflow-auto">
  {content}
</pre>
```

Also used as the fallback when JSON or XML parsing fails.

## Data flow

```
User query
  └─> POST /api/chat (Next.js route)
       └─> POST {AGENT_API_URL}/chat
            └─> AgentSession.run() → raw LLM reply
                 └─> parse_agent_reply() → text + resources[]
                      └─> _fill_missing_content() → downloads CSV/JSON/GeoJSON/TXT/XML/RDF/KML/WMS/WFS/WCS
            ← ChatResponse{ text, resources: [{name, url, format, content}, ...] }
       ← same
  ← same
       │
       ▼
  Message.tsx
    ├─ AssistantMarkdown(text)   ← NEW
    └─ ResourceList → ResourceCard[]
                       ├─ [badge + name + "→ Apri"]   (unchanged)
                       └─ if isPreviewable(format, content):
                            └─ [▸ Mostra anteprima] toggle
                                └─ ResourcePreview(format, content)   ← NEW
                                     ├─ CSV       → CsvTablePreview
                                     ├─ JSON      → JsonPreview
                                     ├─ XML/...   → XmlPreview
                                     └─ else      → TextPreview
```

## Dependencies

Added to `ckan-mcp-ui/package.json`:

```json
{
  "dependencies": {
    "@tanstack/react-virtual": "^3.x",
    "papaparse": "^5.x",
    "react-markdown": "^9.x",
    "remark-gfm": "^4.x"
  },
  "devDependencies": {
    "@types/papaparse": "^5.x"
  }
}
```

Bundle delta ≈ +85 KB gzipped. No syntax-highlighter (Prism/Shiki) — JSON coloring is done with regex + CSS.

## Edge cases & error handling

| Scenario | Behavior |
|---|---|
| Backend download failed → `content === null` | No toggle, only "→ Apri" link (as today). |
| Content truncated at 200 KB | Trailing notice `[…truncated at 200000 bytes; original size N bytes]` is already appended by `_fetch_text`. The preview shows a small `⚠ troncato a 200 KB` badge derived from that marker. |
| Malformed CSV | Yellow banner above the table, render what PapaParse managed. |
| Malformed JSON (e.g. truncation mid-array) | Catch `SyntaxError` → fall back to `TextPreview`. |
| Malformed XML | `DOMParser` returns `<parsererror>` element → fall back to `TextPreview`. |
| Binary format (PDF/XLSX/ZIP/SHP/…) | Card unchanged: badge + name + "→ Apri" only. No toggle. |
| Very wide CSV (many columns) | Container scrolls horizontally; cells `truncate max-w-[20ch]` + `title=` for full value tooltip. |
| Very tall CSV (thousands of rows) | `@tanstack/react-virtual` keeps DOM bounded. |

## Testing plan

**Backend** — `ckan-mcp-agent/tests/test_api.py` (new or extended):

- Mock `httpx.AsyncClient.get` and call `_fill_missing_content` with a `Resource(format="XML", content=None)`. Assert content gets populated.
- Same for `KML`, `RDF`.
- Assert binary format (`PDF`) is **not** downloaded.

**UI** — manual verification scenarios (no test framework in repo today):

1. Query that returns a CSV with `;` separator (e.g. the Comune di Firenze dataset cited in the request). Verify auto-detect, virtualized rendering, header row sticky.
2. Query that returns a GeoJSON resource. Verify JSON pretty-print + coloring.
3. Query that returns a WFS/WMS capabilities URL (XML). Verify XML pretty-print.
4. Query that returns a PDF resource. Verify no preview toggle, only the link.
5. Assistant reply containing markdown (heading + bullet list + table + **bold** + inline `code`). Verify each element renders correctly.
6. Force a malformed JSON (point `JsonPreview` at truncated content) and verify graceful fallback.

## Out-of-scope notes

- Tableau-style filtering/sorting: deferred. The "Anteprima" is a read-only viewer.
- Syntax highlighting via Prism/Shiki: rejected — bundle cost not justified for a secondary viewer.
- Server-side parsing: rejected — keeps backend payload small and decoupled from rendering choices.
- Markdown sanitization with `rehype-sanitize`: `react-markdown` v9 disables raw HTML by default, so unescaped `<script>` in the assistant text cannot reach the DOM. We rely on that default rather than adding `rehype-sanitize` explicitly.
