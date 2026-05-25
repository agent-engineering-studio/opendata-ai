# Resource Preview Inline + Markdown Rendering — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the assistant reply as proper markdown and add format-aware inline previews for downloaded resource content (virtualized CSV table, pretty JSON, pretty XML, monospace text) gated behind a per-card "Anteprima" toggle.

**Architecture:** Two layers. Backend gets a one-line extension to `_DOWNLOADABLE_FORMATS` so XML/RDF/KML/WMS/WFS/WCS are also downloaded. UI gains a `AssistantMarkdown` component (react-markdown + remark-gfm) for assistant text, a `ResourcePreview` dispatcher that picks the right viewer based on `resource.format` (CSV → virtualized table, JSON/GeoJSON → pretty JSON, XML/RDF/KML/WMS/WFS/WCS → pretty XML, TXT → mono text), and a per-card toggle in `ResourceCard`.

**Tech Stack:**
- Backend: Python 3.11+, FastAPI, httpx, pytest (existing)
- UI: Next.js 15 + React 19 + Tailwind 4 (existing); new deps `papaparse`, `@tanstack/react-virtual`, `react-markdown`, `remark-gfm`

**Spec:** `docs/superpowers/specs/2026-05-25-resource-preview-and-markdown-design.md`

---

## File Structure

**New files**
- `ckan-mcp-ui/components/AssistantMarkdown.tsx` — react-markdown wrapper with Tailwind class overrides
- `ckan-mcp-ui/components/preview/ResourcePreview.tsx` — dispatcher + `isPreviewable()` helper
- `ckan-mcp-ui/components/preview/TextPreview.tsx` — monospace `<pre>` fallback
- `ckan-mcp-ui/components/preview/JsonPreview.tsx` — JSON.parse + JSON.stringify + CSS coloring
- `ckan-mcp-ui/components/preview/XmlPreview.tsx` — DOMParser + prettyPrintXml + `<pre>` block
- `ckan-mcp-ui/components/preview/CsvTablePreview.tsx` — PapaParse + react-virtual table
- `ckan-mcp-agent/tests/test_fill_missing_content.py` — unit tests for backend download routing

**Modified files**
- `ckan-mcp-agent/src/ckan_agent/api.py:44` — extend `_DOWNLOADABLE_FORMATS`
- `ckan-mcp-ui/package.json` — add 4 deps + 1 devDep
- `ckan-mcp-ui/app/globals.css` — JSON token color classes
- `ckan-mcp-ui/components/Message.tsx` — assistant text uses `AssistantMarkdown`
- `ckan-mcp-ui/components/ResourceCard.tsx` — add `expanded` state + toggle button + preview render

---

## Task 1: Backend — extend `_DOWNLOADABLE_FORMATS`

**Files:**
- Test: `ckan-mcp-agent/tests/test_fill_missing_content.py` (new)
- Modify: `ckan-mcp-agent/src/ckan_agent/api.py:44`

- [ ] **Step 1: Write the failing test**

Create `ckan-mcp-agent/tests/test_fill_missing_content.py`:

```python
"""Unit tests for _fill_missing_content: which formats trigger a download."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ckan_agent.api import Resource, _fill_missing_content


def _make(fmt: str, content: str | None = None) -> Resource:
    return Resource(
        name=f"file.{fmt.lower()}",
        url=f"https://example.com/file.{fmt.lower()}",
        format=fmt,
        content=content,
    )


@pytest.mark.asyncio
async def test_downloads_csv_json_geojson_txt():
    resources = [_make(f) for f in ("CSV", "JSON", "GEOJSON", "TXT")]
    with patch("ckan_agent.api._fetch_text", new_callable=AsyncMock) as fetch:
        fetch.return_value = "DATA"
        await _fill_missing_content(resources)
    assert all(r.content == "DATA" for r in resources)
    assert fetch.call_count == 4


@pytest.mark.asyncio
async def test_downloads_xml_rdf_kml_wms_wfs_wcs():
    resources = [_make(f) for f in ("XML", "RDF", "KML", "WMS", "WFS", "WCS")]
    with patch("ckan_agent.api._fetch_text", new_callable=AsyncMock) as fetch:
        fetch.return_value = "<root/>"
        await _fill_missing_content(resources)
    assert all(r.content == "<root/>" for r in resources)
    assert fetch.call_count == 6


@pytest.mark.asyncio
async def test_skips_binary_formats():
    resources = [_make(f) for f in ("PDF", "XLSX", "ZIP", "SHP")]
    with patch("ckan_agent.api._fetch_text", new_callable=AsyncMock) as fetch:
        await _fill_missing_content(resources)
    assert all(r.content is None for r in resources)
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_skips_when_content_already_present():
    resources = [_make("CSV", content="already,here")]
    with patch("ckan_agent.api._fetch_text", new_callable=AsyncMock) as fetch:
        await _fill_missing_content(resources)
    assert resources[0].content == "already,here"
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_format_match_is_case_insensitive():
    resources = [_make("xml"), _make("Csv")]
    with patch("ckan_agent.api._fetch_text", new_callable=AsyncMock) as fetch:
        fetch.return_value = "X"
        await _fill_missing_content(resources)
    assert fetch.call_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run from `ckan-mcp-agent/`:

```bash
pytest tests/test_fill_missing_content.py -v
```

Expected: `test_downloads_xml_rdf_kml_wms_wfs_wcs` FAILS with `fetch.call_count == 0` (XML/RDF/KML/WMS/WFS/WCS are not yet in `_DOWNLOADABLE_FORMATS`). The other tests should already pass.

- [ ] **Step 3: Apply the minimal source change**

Modify `ckan-mcp-agent/src/ckan_agent/api.py:44`, replace the single line:

```python
_DOWNLOADABLE_FORMATS = frozenset({"CSV", "JSON", "GEOJSON", "TXT"})
```

with:

```python
_DOWNLOADABLE_FORMATS = frozenset({
    "CSV", "JSON", "GEOJSON", "TXT",
    "XML", "RDF", "KML", "WMS", "WFS", "WCS",
})
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_fill_missing_content.py -v
pytest tests/ -v
```

Expected: all green, including the existing `test_api_parsing.py`.

- [ ] **Step 5: Commit**

```bash
git add ckan-mcp-agent/src/ckan_agent/api.py ckan-mcp-agent/tests/test_fill_missing_content.py
git commit -m "feat(api): also auto-download XML/RDF/KML/WMS/WFS/WCS resources"
```

---

## Task 2: UI — install dependencies

**Files:**
- Modify: `ckan-mcp-ui/package.json`, `ckan-mcp-ui/package-lock.json`

- [ ] **Step 1: Install runtime + types**

Run from `ckan-mcp-ui/`:

```bash
npm install papaparse@^5 react-markdown@^9 remark-gfm@^4 @tanstack/react-virtual@^3
npm install --save-dev @types/papaparse@^5
```

- [ ] **Step 2: Verify the project still typechecks and builds**

```bash
npm run typecheck
npm run build
```

Expected: both succeed without errors.

- [ ] **Step 3: Commit**

```bash
git add ckan-mcp-ui/package.json ckan-mcp-ui/package-lock.json
git commit -m "chore(ui): add papaparse, react-markdown, remark-gfm, react-virtual"
```

---

## Task 3: UI — `AssistantMarkdown` component

**Files:**
- Create: `ckan-mcp-ui/components/AssistantMarkdown.tsx`
- Modify: `ckan-mcp-ui/components/Message.tsx` (replace `Paragraphs` usage for assistant role)

- [ ] **Step 1: Create `AssistantMarkdown.tsx`**

Create `ckan-mcp-ui/components/AssistantMarkdown.tsx`:

```tsx
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

const components: Components = {
  h1: ({ children }) => (
    <h1 className="mb-1 mt-3 text-lg font-semibold text-slate-900">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-1 mt-3 text-base font-semibold text-slate-900">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-1 mt-3 text-sm font-semibold text-slate-900">{children}</h3>
  ),
  p: ({ children }) => <p className="leading-relaxed">{children}</p>,
  ul: ({ children }) => (
    <ul className="list-disc space-y-1 pl-5">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal space-y-1 pl-5">{children}</ol>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-4 border-slate-300 pl-3 italic text-slate-600">
      {children}
    </blockquote>
  ),
  code: ({ className, children, ...props }) => {
    const isBlock = /language-/.test(className ?? "");
    if (isBlock) {
      return (
        <code className="font-mono text-sm" {...props}>
          {children}
        </code>
      );
    }
    return (
      <code
        className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[0.85em]"
        {...props}
      >
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="overflow-auto rounded-md bg-slate-900 p-3 text-sm text-slate-100">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="overflow-auto">
      <table className="border-collapse text-sm">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-slate-200 bg-slate-50 px-2 py-1 text-left font-semibold">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-slate-200 px-2 py-1">{children}</td>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-blue-700 underline hover:text-blue-900"
    >
      {children}
    </a>
  ),
};

export function AssistantMarkdown({ text }: { text: string }) {
  return (
    <div className="space-y-2">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {text}
      </ReactMarkdown>
    </div>
  );
}
```

- [ ] **Step 2: Wire into `Message.tsx`**

Modify `ckan-mcp-ui/components/Message.tsx`. Replace the entire file with:

```tsx
import type { ChatMessage } from "@/lib/types";
import { AssistantMarkdown } from "./AssistantMarkdown";
import { ResourceList } from "./ResourceList";

function Paragraphs({ text }: { text: string }) {
  const blocks = text
    .split(/\n{2,}/)
    .map((b) => b.trim())
    .filter(Boolean);
  if (blocks.length === 0) return null;
  return (
    <div className="space-y-2">
      {blocks.map((block, i) => (
        <p key={i} className="whitespace-pre-wrap leading-relaxed">
          {block}
        </p>
      ))}
    </div>
  );
}

export function Message({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-blue-600 px-4 py-2 text-white">
          <Paragraphs text={message.text} />
        </div>
      </div>
    );
  }

  if (message.role === "error") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[80%] rounded-2xl rounded-bl-sm border border-red-300 bg-red-50 px-4 py-2 text-red-800">
          <Paragraphs text={message.text} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[90%] rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-3 text-slate-800 shadow-sm">
        <AssistantMarkdown text={message.text} />
        <ResourceList resources={message.resources} />
        <div className="mt-3 text-xs text-slate-400">
          ⏱ {(message.durationMs / 1000).toFixed(1)}s
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Run typecheck + lint**

```bash
npm run typecheck
npm run lint
```

Expected: both clean.

- [ ] **Step 4: Commit**

```bash
git add ckan-mcp-ui/components/AssistantMarkdown.tsx ckan-mcp-ui/components/Message.tsx
git commit -m "feat(ui): render assistant text with react-markdown + remark-gfm"
```

---

## Task 4: UI — `TextPreview` (fallback building block)

**Files:**
- Create: `ckan-mcp-ui/components/preview/TextPreview.tsx`

- [ ] **Step 1: Create the file**

Create `ckan-mcp-ui/components/preview/TextPreview.tsx`:

```tsx
export function TextPreview({ content }: { content: string }) {
  return (
    <pre className="max-h-96 overflow-auto rounded bg-slate-50 p-3 font-mono text-xs break-words whitespace-pre-wrap text-slate-800">
      {content}
    </pre>
  );
}
```

- [ ] **Step 2: Run typecheck**

```bash
npm run typecheck
```

Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add ckan-mcp-ui/components/preview/TextPreview.tsx
git commit -m "feat(ui): add TextPreview component (TXT viewer + fallback)"
```

---

## Task 5: UI — `JsonPreview` with CSS-only token coloring

**Files:**
- Modify: `ckan-mcp-ui/app/globals.css`
- Create: `ckan-mcp-ui/components/preview/JsonPreview.tsx`

- [ ] **Step 1: Add JSON token color classes to `globals.css`**

Replace `ckan-mcp-ui/app/globals.css` with:

```css
@import "tailwindcss";

@layer base {
  html,
  body {
    height: 100%;
    background-color: #f8fafc;
    color: #0f172a;
  }
}

@layer components {
  .json-key {
    color: #0369a1;
  }
  .json-string {
    color: #15803d;
  }
  .json-number {
    color: #b45309;
  }
  .json-boolean {
    color: #7c3aed;
  }
  .json-null {
    color: #64748b;
    font-style: italic;
  }
}
```

- [ ] **Step 2: Create `JsonPreview.tsx`**

Create `ckan-mcp-ui/components/preview/JsonPreview.tsx`:

```tsx
import { Fragment } from "react";
import { TextPreview } from "./TextPreview";

const TOKEN_RE =
  /("(?:\\.|[^"\\])*")(\s*:)?|(\b-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|(\btrue\b|\bfalse\b)|(\bnull\b)/g;

function tokenize(pretty: string) {
  const nodes: React.ReactNode[] = [];
  let lastIndex = 0;
  let i = 0;
  for (const m of pretty.matchAll(TOKEN_RE)) {
    const start = m.index ?? 0;
    if (start > lastIndex) {
      nodes.push(<Fragment key={`t${i++}`}>{pretty.slice(lastIndex, start)}</Fragment>);
    }
    const [, strLit, isKey, num, bool, nul] = m;
    if (strLit !== undefined) {
      if (isKey) {
        nodes.push(
          <span key={`k${i++}`} className="json-key">
            {strLit}
          </span>,
          <Fragment key={`c${i++}`}>{isKey}</Fragment>,
        );
      } else {
        nodes.push(
          <span key={`s${i++}`} className="json-string">
            {strLit}
          </span>,
        );
      }
    } else if (num !== undefined) {
      nodes.push(
        <span key={`n${i++}`} className="json-number">
          {num}
        </span>,
      );
    } else if (bool !== undefined) {
      nodes.push(
        <span key={`b${i++}`} className="json-boolean">
          {bool}
        </span>,
      );
    } else if (nul !== undefined) {
      nodes.push(
        <span key={`x${i++}`} className="json-null">
          {nul}
        </span>,
      );
    }
    lastIndex = start + m[0].length;
  }
  if (lastIndex < pretty.length) {
    nodes.push(<Fragment key={`t${i++}`}>{pretty.slice(lastIndex)}</Fragment>);
  }
  return nodes;
}

export function JsonPreview({ content }: { content: string }) {
  try {
    const obj = JSON.parse(content);
    const pretty = JSON.stringify(obj, null, 2);
    return (
      <pre className="max-h-96 overflow-auto rounded bg-slate-900 p-3 font-mono text-xs whitespace-pre text-slate-100">
        {tokenize(pretty)}
      </pre>
    );
  } catch {
    return <TextPreview content={content} />;
  }
}
```

- [ ] **Step 3: Run typecheck + lint**

```bash
npm run typecheck
npm run lint
```

Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add ckan-mcp-ui/app/globals.css ckan-mcp-ui/components/preview/JsonPreview.tsx
git commit -m "feat(ui): add JsonPreview with inline token coloring"
```

---

## Task 6: UI — `XmlPreview` with depth-indented pretty printer

**Files:**
- Create: `ckan-mcp-ui/components/preview/XmlPreview.tsx`

- [ ] **Step 1: Create the file**

Create `ckan-mcp-ui/components/preview/XmlPreview.tsx`:

```tsx
import { TextPreview } from "./TextPreview";

function prettyPrintXml(node: Node, depth = 0): string {
  const indent = "  ".repeat(depth);

  if (node.nodeType === Node.TEXT_NODE) {
    const text = (node.nodeValue ?? "").trim();
    return text ? `${indent}${text}\n` : "";
  }

  if (node.nodeType === Node.COMMENT_NODE) {
    return `${indent}<!--${node.nodeValue ?? ""}-->\n`;
  }

  if (node.nodeType !== Node.ELEMENT_NODE) {
    return "";
  }

  const el = node as Element;
  const attrs = Array.from(el.attributes)
    .map((a) => ` ${a.name}="${a.value}"`)
    .join("");

  const children = Array.from(el.childNodes);
  const hasElementChild = children.some((c) => c.nodeType === Node.ELEMENT_NODE);
  const textOnly =
    children.length === 1 && children[0].nodeType === Node.TEXT_NODE;

  if (children.length === 0) {
    return `${indent}<${el.tagName}${attrs}/>\n`;
  }

  if (textOnly && !hasElementChild) {
    const text = (children[0].nodeValue ?? "").trim();
    return `${indent}<${el.tagName}${attrs}>${text}</${el.tagName}>\n`;
  }

  let out = `${indent}<${el.tagName}${attrs}>\n`;
  for (const child of children) {
    out += prettyPrintXml(child, depth + 1);
  }
  out += `${indent}</${el.tagName}>\n`;
  return out;
}

export function XmlPreview({ content }: { content: string }) {
  if (typeof window === "undefined" || typeof DOMParser === "undefined") {
    return <TextPreview content={content} />;
  }
  try {
    const doc = new DOMParser().parseFromString(content, "application/xml");
    if (doc.querySelector("parsererror")) {
      return <TextPreview content={content} />;
    }
    const pretty = prettyPrintXml(doc.documentElement).trimEnd();
    return (
      <pre className="max-h-96 overflow-auto rounded bg-slate-900 p-3 font-mono text-xs whitespace-pre text-slate-100">
        {pretty}
      </pre>
    );
  } catch {
    return <TextPreview content={content} />;
  }
}
```

- [ ] **Step 2: Run typecheck + lint**

```bash
npm run typecheck
npm run lint
```

Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add ckan-mcp-ui/components/preview/XmlPreview.tsx
git commit -m "feat(ui): add XmlPreview with depth-indented pretty printer"
```

---

## Task 7: UI — `CsvTablePreview` with PapaParse + react-virtual

**Files:**
- Create: `ckan-mcp-ui/components/preview/CsvTablePreview.tsx`

- [ ] **Step 1: Create the file**

Create `ckan-mcp-ui/components/preview/CsvTablePreview.tsx`:

```tsx
"use client";

import { useMemo, useRef } from "react";
import Papa from "papaparse";
import { useVirtualizer } from "@tanstack/react-virtual";

type ParsedCsv = {
  fields: string[];
  rows: Record<string, string>[];
  errors: number;
};

function parseCsv(content: string): ParsedCsv {
  const result = Papa.parse<Record<string, string>>(content, {
    header: true,
    delimiter: "",
    skipEmptyLines: true,
    dynamicTyping: false,
  });
  const fields = (result.meta.fields ?? []).filter(
    (f): f is string => typeof f === "string" && f.length > 0,
  );
  const rows = (result.data ?? []).filter(
    (r): r is Record<string, string> => r != null && typeof r === "object",
  );
  return { fields, rows, errors: result.errors.length };
}

const ROW_HEIGHT = 32;

export function CsvTablePreview({ content }: { content: string }) {
  const { fields, rows, errors } = useMemo(() => parseCsv(content), [content]);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 8,
  });

  if (fields.length === 0) {
    return (
      <pre className="max-h-96 overflow-auto rounded bg-slate-50 p-3 font-mono text-xs whitespace-pre-wrap text-slate-800">
        {content}
      </pre>
    );
  }

  return (
    <div className="space-y-2">
      {errors > 0 ? (
        <div className="rounded border border-yellow-300 bg-yellow-50 px-3 py-1 text-xs text-yellow-800">
          Formato CSV non standard — alcune righe potrebbero essere errate
          ({errors} segnalazion{errors === 1 ? "e" : "i"})
        </div>
      ) : null}
      <div className="text-xs text-slate-500">
        {rows.length} righ{rows.length === 1 ? "a" : "e"} · {fields.length}{" "}
        colonn{fields.length === 1 ? "a" : "e"}
      </div>
      <div
        ref={scrollRef}
        className="max-h-96 overflow-auto rounded border border-slate-200"
      >
        <table className="w-full border-collapse text-xs">
          <thead className="sticky top-0 bg-slate-100">
            <tr>
              {fields.map((f) => (
                <th
                  key={f}
                  className="border-b border-slate-200 px-2 py-1 text-left font-semibold text-slate-700"
                >
                  {f}
                </th>
              ))}
            </tr>
          </thead>
          <tbody
            style={{
              position: "relative",
              height: virtualizer.getTotalSize(),
              display: "block",
            }}
          >
            {virtualizer.getVirtualItems().map((vi) => {
              const row = rows[vi.index];
              return (
                <tr
                  key={vi.key}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    height: vi.size,
                    transform: `translateY(${vi.start}px)`,
                    display: "table",
                    tableLayout: "fixed",
                  }}
                >
                  {fields.map((f) => {
                    const value = row?.[f] ?? "";
                    return (
                      <td
                        key={f}
                        title={value}
                        className="overflow-hidden text-ellipsis whitespace-nowrap border-b border-slate-100 px-2 py-1"
                      >
                        {value}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Run typecheck + lint**

```bash
npm run typecheck
npm run lint
```

Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add ckan-mcp-ui/components/preview/CsvTablePreview.tsx
git commit -m "feat(ui): add CsvTablePreview with PapaParse + react-virtual"
```

---

## Task 8: UI — `ResourcePreview` dispatcher + `isPreviewable`

**Files:**
- Create: `ckan-mcp-ui/components/preview/ResourcePreview.tsx`

- [ ] **Step 1: Create the file**

Create `ckan-mcp-ui/components/preview/ResourcePreview.tsx`:

```tsx
import { CsvTablePreview } from "./CsvTablePreview";
import { JsonPreview } from "./JsonPreview";
import { TextPreview } from "./TextPreview";
import { XmlPreview } from "./XmlPreview";

const TEXTUAL_FORMATS = new Set([
  "CSV",
  "JSON",
  "GEOJSON",
  "TXT",
  "XML",
  "RDF",
  "KML",
  "WMS",
  "WFS",
  "WCS",
]);

const XML_FAMILY = new Set(["XML", "RDF", "KML", "WMS", "WFS", "WCS"]);

export function isPreviewable(
  format: string | undefined,
  content: string | null | undefined,
): content is string {
  if (!content || !format) return false;
  return TEXTUAL_FORMATS.has(format.toUpperCase());
}

export function ResourcePreview({
  format,
  content,
}: {
  format: string;
  content: string;
}) {
  const f = format.toUpperCase();
  if (!TEXTUAL_FORMATS.has(f)) return null;
  if (f === "CSV") return <CsvTablePreview content={content} />;
  if (f === "JSON" || f === "GEOJSON") return <JsonPreview content={content} />;
  if (XML_FAMILY.has(f)) return <XmlPreview content={content} />;
  return <TextPreview content={content} />;
}
```

- [ ] **Step 2: Run typecheck**

```bash
npm run typecheck
```

Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add ckan-mcp-ui/components/preview/ResourcePreview.tsx
git commit -m "feat(ui): add ResourcePreview dispatcher + isPreviewable helper"
```

---

## Task 9: UI — `ResourceCard` toggle + preview integration

**Files:**
- Modify: `ckan-mcp-ui/components/ResourceCard.tsx`

- [ ] **Step 1: Replace `ResourceCard.tsx`**

Replace the entire content of `ckan-mcp-ui/components/ResourceCard.tsx` with:

```tsx
"use client";

import { useState } from "react";
import type { Resource } from "@/lib/types";
import { ResourcePreview, isPreviewable } from "./preview/ResourcePreview";

function formatBadgeColor(format: string): string {
  const f = format.toUpperCase();
  if (["CSV", "JSON", "XLSX", "XLS"].includes(f))
    return "bg-blue-100 text-blue-800";
  if (["GEOJSON", "SHP", "KML", "WMS", "GPKG"].includes(f))
    return "bg-emerald-100 text-emerald-800";
  return "bg-slate-100 text-slate-700";
}

export function ResourceCard({ resource }: { resource: Resource }) {
  const [expanded, setExpanded] = useState(false);
  const display = resource.name || resource.url || "(senza nome)";
  const badge = resource.format?.trim() ? resource.format.toUpperCase() : "—";
  const canPreview = isPreviewable(resource.format, resource.content);

  return (
    <div className="rounded-md border border-slate-200 bg-white">
      <div className="flex items-center gap-3 px-3 py-2">
        <span
          className={`inline-flex min-w-[3.5rem] justify-center rounded px-2 py-0.5 font-mono text-xs ${formatBadgeColor(badge)}`}
        >
          {badge}
        </span>
        <span className="flex-1 truncate text-sm text-slate-800">{display}</span>
        {resource.url ? (
          <a
            href={resource.url}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 text-sm font-medium text-blue-700 hover:text-blue-900"
          >
            → Apri
          </a>
        ) : null}
      </div>

      {canPreview ? (
        <div className="border-t border-slate-100 px-3 py-1.5">
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="text-xs font-medium text-slate-600 hover:text-slate-900"
            aria-expanded={expanded}
          >
            {expanded ? "▾ Nascondi anteprima" : "▸ Mostra anteprima"}
          </button>
          {expanded ? (
            <div className="mt-2">
              <ResourcePreview
                format={resource.format}
                content={resource.content as string}
              />
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 2: Run typecheck + lint + build**

```bash
npm run typecheck
npm run lint
npm run build
```

Expected: all three succeed.

- [ ] **Step 3: Commit**

```bash
git add ckan-mcp-ui/components/ResourceCard.tsx
git commit -m "feat(ui): per-card 'Anteprima' toggle wired to ResourcePreview"
```

---

## Task 10: End-to-end manual verification

This task is verification only — no code changes. Do not commit.

- [ ] **Step 1: Start the agent API**

From `ckan-mcp-agent/`:

```bash
ckan-agent-api
```

Expected: server listening on the port from `.env` (default `8002`). Leave it running.

- [ ] **Step 2: Start the UI dev server**

From `ckan-mcp-ui/`, in a separate shell:

```bash
npm run dev
```

Expected: Next.js dev server on `http://localhost:3000`.

- [ ] **Step 3: Verify markdown rendering**

Open `http://localhost:3000`. Ask a query that triggers a richly-formatted reply, e.g.:

> "Elenca i primi 3 dataset disponibili in formato lista numerata con il nome in **grassetto**."

Verify in the chat bubble:
- Bullet/numbered lists render with bullets/numbers (not as `1.` text).
- `**bold**` renders in bold weight.
- Inline `` `code` `` renders with a light gray background.

- [ ] **Step 4: Verify CSV preview**

Ask:

> "Mostrami i dettagli del dataset 2908fe96-58c4-40fe-8b29-9d4d78715ba7"

(or any query returning a CSV resource from a CKAN portal with `;` separator)

Verify:
- The resource card shows `▸ Mostra anteprima` below the link.
- Clicking it expands a virtualized table.
- The header row stays sticky when scrolling.
- The `;` separator is auto-detected (one column per logical field, not one giant column).
- The footer shows `N righe · M colonne`.

- [ ] **Step 5: Verify JSON / GeoJSON preview**

Ask a query that returns a GeoJSON resource. Verify:
- Clicking `▸ Mostra anteprima` shows an indented JSON dump on a dark background.
- Keys are blue, strings green, numbers amber, `true/false` violet, `null` italic gray.

- [ ] **Step 6: Verify XML preview**

Ask a query that returns a WMS/WFS capabilities URL (or any XML/KML/RDF resource). Verify:
- Clicking `▸ Mostra anteprima` shows indented XML on a dark background.
- Self-closing tags and text-only elements render on a single line.

- [ ] **Step 7: Verify binary formats have no toggle**

Ask a query returning a PDF or XLSX resource. Verify:
- The card shows only badge + name + "→ Apri".
- No `▸ Mostra anteprima` button is present.

- [ ] **Step 8: Verify malformed content fallback (optional sanity check)**

In DevTools, edit a CSV resource's content via React DevTools to inject `"a","b\n"unclosed` and verify the yellow banner appears above the table without crashing the UI.

---

## Self-Review Checklist (post-write)

- [x] **Spec coverage:** Each spec section has a corresponding task.
  - Backend `_DOWNLOADABLE_FORMATS` extension → Task 1
  - Dependencies → Task 2
  - `AssistantMarkdown` (markdown rendering) → Task 3
  - `TextPreview` → Task 4
  - `JsonPreview` (JSON/GeoJSON) → Task 5
  - `XmlPreview` (XML/RDF/KML/WMS/WFS/WCS) → Task 6
  - `CsvTablePreview` (virtualized) → Task 7
  - `ResourcePreview` dispatcher → Task 8
  - `ResourceCard` toggle → Task 9
  - Manual verification (all 6 scenarios from spec §6) → Task 10
- [x] **No placeholders.** Each step has the actual code or command.
- [x] **Type consistency.** `Resource` shape comes from `lib/types.ts` (unchanged). `isPreviewable(format, content)` is a type predicate narrowing `content` to `string`, consistent with its use in `ResourceCard`. `ResourcePreview` and all leaf previews take `{ content: string }` (CSV/JSON/XML/Text) or `{ format, content }` (dispatcher only).
