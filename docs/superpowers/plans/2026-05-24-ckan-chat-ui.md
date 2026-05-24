# CKAN Chat UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Next.js web UI under `ckan-mcp-ui/` that demonstrates the CKAN MCP agent via a chat page, wired into the existing `docker-compose.yml` stack.

**Architecture:** A thin Next.js (App Router, TypeScript) client. The browser talks only to a Next.js API route (`/api/chat`), which proxies server-side to `ckan-agent:8002/chat`. State lives in a single client page; resources are rendered as cards with an external link (no inline content preview).

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS v4, Node 20 (multi-stage Docker build).

**Testing strategy:** No automated component tests (per spec § 10 — overhead not justified for a demo). Each task ends with a TypeScript check (`npx tsc --noEmit`) when types or components change, and a final manual smoke test sequence validates end-to-end behavior. All commands assume PowerShell — Bash equivalents are noted only where they differ.

**Reference spec:** `docs/superpowers/specs/2026-05-24-ckan-chat-ui-design.md`

---

## File map (created or modified)

**Created:**
- `ckan-mcp-ui/package.json` — deps + scripts
- `ckan-mcp-ui/tsconfig.json` — strict TS config
- `ckan-mcp-ui/next.config.ts` — `output: 'standalone'`
- `ckan-mcp-ui/postcss.config.mjs` — Tailwind v4 plugin
- `ckan-mcp-ui/.env.local.example`
- `ckan-mcp-ui/.gitignore`
- `ckan-mcp-ui/.dockerignore`
- `ckan-mcp-ui/Dockerfile` — multi-stage Node 20-alpine
- `ckan-mcp-ui/README.md` — local dev + smoke test checklist
- `ckan-mcp-ui/app/layout.tsx`
- `ckan-mcp-ui/app/globals.css`
- `ckan-mcp-ui/app/page.tsx`
- `ckan-mcp-ui/app/api/chat/route.ts`
- `ckan-mcp-ui/components/ChatHeader.tsx`
- `ckan-mcp-ui/components/PortalSelect.tsx`
- `ckan-mcp-ui/components/ExampleQueries.tsx`
- `ckan-mcp-ui/components/MessageList.tsx`
- `ckan-mcp-ui/components/Message.tsx`
- `ckan-mcp-ui/components/ResourceList.tsx`
- `ckan-mcp-ui/components/ResourceCard.tsx`
- `ckan-mcp-ui/components/ChatInput.tsx`
- `ckan-mcp-ui/lib/types.ts`
- `ckan-mcp-ui/lib/examples.ts`
- `ckan-mcp-ui/lib/portals.ts`

**Modified:**
- `docker-compose.yml` — add `ckan-ui` service
- `README.md` — mention the UI in the "Endpoints exposed on the host" table

---

## Task 1: Scaffold the Next.js project (no code yet)

**Files:**
- Create: `ckan-mcp-ui/package.json`
- Create: `ckan-mcp-ui/tsconfig.json`
- Create: `ckan-mcp-ui/next.config.ts`
- Create: `ckan-mcp-ui/postcss.config.mjs`
- Create: `ckan-mcp-ui/.gitignore`
- Create: `ckan-mcp-ui/.dockerignore`
- Create: `ckan-mcp-ui/.env.local.example`
- Create: `ckan-mcp-ui/app/globals.css`

- [ ] **Step 1: Create `ckan-mcp-ui/package.json`**

```json
{
  "name": "ckan-mcp-ui",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev -p 3000",
    "build": "next build",
    "start": "next start -p 3000",
    "lint": "next lint",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "next": "15.1.4",
    "react": "19.0.0",
    "react-dom": "19.0.0"
  },
  "devDependencies": {
    "@types/node": "22.10.5",
    "@types/react": "19.0.4",
    "@types/react-dom": "19.0.2",
    "@tailwindcss/postcss": "^4.0.0",
    "eslint": "9.18.0",
    "eslint-config-next": "15.1.4",
    "tailwindcss": "^4.0.0",
    "typescript": "5.7.3"
  }
}
```

- [ ] **Step 2: Create `ckan-mcp-ui/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "ES2022"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": {
      "@/*": ["./*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Create `ckan-mcp-ui/next.config.ts`**

```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
};

export default nextConfig;
```

- [ ] **Step 4: Create `ckan-mcp-ui/postcss.config.mjs`**

```js
export default {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};
```

- [ ] **Step 5: Create `ckan-mcp-ui/.gitignore`**

```
node_modules
.next
out
.env.local
*.tsbuildinfo
next-env.d.ts
```

- [ ] **Step 6: Create `ckan-mcp-ui/.dockerignore`**

```
node_modules
.next
.git
.env.local
README.md
Dockerfile
.dockerignore
```

- [ ] **Step 7: Create `ckan-mcp-ui/.env.local.example`**

```
# URL of the ckan-mcp-agent HTTP API
# - dev (host):     http://localhost:8002
# - compose:        http://ckan-agent:8002
AGENT_API_URL=http://localhost:8002
```

- [ ] **Step 8: Create `ckan-mcp-ui/app/globals.css`**

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
```

- [ ] **Step 9: Install dependencies**

Run from `ckan-mcp-ui/`:
```
npm install
```
Expected: creates `node_modules/` and `package-lock.json` without errors. (If `npm` is not available locally, this step still needs to succeed inside the Docker build — but installing locally is the fastest feedback loop.)

- [ ] **Step 10: Commit**

```
git add ckan-mcp-ui/package.json ckan-mcp-ui/package-lock.json ckan-mcp-ui/tsconfig.json ckan-mcp-ui/next.config.ts ckan-mcp-ui/postcss.config.mjs ckan-mcp-ui/.gitignore ckan-mcp-ui/.dockerignore ckan-mcp-ui/.env.local.example ckan-mcp-ui/app/globals.css
git commit -m "feat(ui): scaffold Next.js app under ckan-mcp-ui/"
```

---

## Task 2: Define types and shared data

**Files:**
- Create: `ckan-mcp-ui/lib/types.ts`
- Create: `ckan-mcp-ui/lib/portals.ts`
- Create: `ckan-mcp-ui/lib/examples.ts`

- [ ] **Step 1: Create `ckan-mcp-ui/lib/types.ts`**

```ts
export type Resource = {
  name: string;
  url: string;
  format: string;
  content: string | null;
};

export type ChatRequest = {
  query: string;
  base_url?: string;
};

export type ChatResponse = {
  text: string;
  resources: Resource[];
};

export type ChatMessage =
  | { role: "user"; text: string }
  | {
      role: "assistant";
      text: string;
      resources: Resource[];
      durationMs: number;
    }
  | { role: "error"; text: string };
```

- [ ] **Step 2: Create `ckan-mcp-ui/lib/portals.ts`**

```ts
export type PortalPreset = {
  label: string;
  url: string;
};

export const PORTAL_PRESETS: PortalPreset[] = [
  { label: "dati.gov.it (default)", url: "https://www.dati.gov.it/opendata" },
  { label: "data.gov.uk", url: "https://data.gov.uk" },
  { label: "data.gov (US)", url: "https://data.gov" },
  { label: "open.canada.ca", url: "https://open.canada.ca/data/en" },
  { label: "data.gov.au", url: "https://data.gov.au" },
];

export const DEFAULT_PORTAL = PORTAL_PRESETS[0].url;

export const CUSTOM_PORTAL_VALUE = "__custom__";
```

- [ ] **Step 3: Create `ckan-mcp-ui/lib/examples.ts`**

```ts
export type ExampleQuery = {
  label: string;
  query: string;
};

export const EXAMPLE_QUERIES: ExampleQuery[] = [
  {
    label: "5 dataset più recenti",
    query: "Mostrami i 5 dataset più recenti su dati.gov.it",
  },
  {
    label: "Trasporti su data.gov.uk",
    query: "List recent datasets about transport",
  },
  {
    label: "Dettagli di un dataset (UUID)",
    query:
      "Mostrami i dettagli del dataset 2908fe96-58c4-40fe-8b29-9d4d78715ba7",
  },
  {
    label: "Organizzazioni per tema trasporti",
    query: "Quali organizzazioni pubblicano dati su trasporti?",
  },
  {
    label: "Stato del portale CKAN",
    query: "Show CKAN portal status",
  },
];
```

- [ ] **Step 4: Verify TypeScript compiles**

Run from `ckan-mcp-ui/`:
```
npx tsc --noEmit
```
Expected: exit code 0, no output. (May complain about missing `app/layout.tsx` — that's addressed in Task 3. If only missing-layout errors are reported, proceed.)

- [ ] **Step 5: Commit**

```
git add ckan-mcp-ui/lib/
git commit -m "feat(ui): add ChatResponse types, portal presets, and example queries"
```

---

## Task 3: Root layout and a placeholder page

**Files:**
- Create: `ckan-mcp-ui/app/layout.tsx`
- Create: `ckan-mcp-ui/app/page.tsx` (placeholder; real wiring in Task 11)

- [ ] **Step 1: Create `ckan-mcp-ui/app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CKAN MCP Agent — Demo",
  description:
    "Chat UI demo for the CKAN MCP server + Microsoft Agent Framework agent",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="it">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
```

- [ ] **Step 2: Create placeholder `ckan-mcp-ui/app/page.tsx`**

```tsx
export default function Page() {
  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-2xl font-semibold">CKAN MCP Agent — Demo</h1>
      <p className="mt-2 text-slate-600">
        UI scaffold in place. Wiring follows in subsequent tasks.
      </p>
    </main>
  );
}
```

- [ ] **Step 3: Run dev server to confirm the scaffold boots**

Run from `ckan-mcp-ui/`:
```
npm run dev
```
Expected: server starts on `http://localhost:3000` with no errors. Open in browser → see the title and the placeholder text. Stop the server with Ctrl+C.

- [ ] **Step 4: Typecheck**

```
npx tsc --noEmit
```
Expected: exit code 0.

- [ ] **Step 5: Commit**

```
git add ckan-mcp-ui/app/layout.tsx ckan-mcp-ui/app/page.tsx
git commit -m "feat(ui): add root layout and placeholder home page"
```

---

## Task 4: API proxy route

**Files:**
- Create: `ckan-mcp-ui/app/api/chat/route.ts`

This is the only file that knows about `AGENT_API_URL`. It runs server-side, so there is no CORS issue. Per spec § 7, timeout is 120s and any error becomes a 502 with `{ error }` body.

- [ ] **Step 1: Create `ckan-mcp-ui/app/api/chat/route.ts`**

```ts
import { NextRequest, NextResponse } from "next/server";
import type { ChatRequest, ChatResponse } from "@/lib/types";

const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://localhost:8002";
const TIMEOUT_MS = 120_000;

export const runtime = "nodejs";

export async function POST(req: NextRequest): Promise<NextResponse> {
  let body: ChatRequest;
  try {
    body = (await req.json()) as ChatRequest;
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON in request body" },
      { status: 400 },
    );
  }

  if (!body?.query || typeof body.query !== "string") {
    return NextResponse.json(
      { error: "Missing 'query' field" },
      { status: 400 },
    );
  }

  const upstreamUrl = `${AGENT_API_URL.replace(/\/$/, "")}/chat`;

  try {
    const upstream = await fetch(upstreamUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });

    const text = await upstream.text();

    if (!upstream.ok) {
      const excerpt = text.slice(0, 500);
      console.error(
        `[api/chat] upstream ${upstream.status} ${upstream.statusText}: ${excerpt}`,
      );
      return NextResponse.json(
        {
          error: `Backend ${upstream.status}: ${excerpt || upstream.statusText}`,
        },
        { status: 502 },
      );
    }

    let json: ChatResponse;
    try {
      json = JSON.parse(text) as ChatResponse;
    } catch (e) {
      console.error(
        `[api/chat] upstream returned non-JSON body:`,
        text.slice(0, 500),
      );
      return NextResponse.json(
        { error: "Backend returned a non-JSON response" },
        { status: 502 },
      );
    }

    return NextResponse.json(json, { status: 200 });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    const isTimeout = message.toLowerCase().includes("timeout");
    console.error(`[api/chat] transport error:`, err);
    return NextResponse.json(
      {
        error: isTimeout
          ? `Timeout dopo ${TIMEOUT_MS / 1000}s — l'agent non ha risposto in tempo`
          : `Backend non raggiungibile: ${message}`,
      },
      { status: 502 },
    );
  }
}
```

- [ ] **Step 2: Smoke-test the route against the running agent**

Pre-req: `make up` is running and `ckan-agent` is healthy on `:8002`.

Run from `ckan-mcp-ui/`:
```
npm run dev
```
In a separate terminal (PowerShell):
```
Invoke-RestMethod -Method Post -Uri http://localhost:3000/api/chat -ContentType 'application/json' -Body '{"query":"Show CKAN portal status"}'
```
Expected: a JSON object with `text` (string) and `resources` (array). Stop the dev server.

Bash equivalent:
```
curl -sS -X POST http://localhost:3000/api/chat -H 'Content-Type: application/json' -d '{"query":"Show CKAN portal status"}'
```

- [ ] **Step 3: Smoke-test the error path**

Stop `ckan-agent`:
```
docker compose stop ckan-agent
```
Re-run the same `Invoke-RestMethod`. Expected: an HTTP error containing `{"error":"Backend non raggiungibile: ..."}`. Restart the agent:
```
docker compose start ckan-agent
```

- [ ] **Step 4: Typecheck**

```
npx tsc --noEmit
```
Expected: exit code 0.

- [ ] **Step 5: Commit**

```
git add ckan-mcp-ui/app/api/chat/route.ts
git commit -m "feat(ui): add /api/chat proxy route with 120s timeout and 502 mapping"
```

---

## Task 5: `ResourceCard` and `ResourceList`

**Files:**
- Create: `ckan-mcp-ui/components/ResourceCard.tsx`
- Create: `ckan-mcp-ui/components/ResourceList.tsx`

Per spec § 4: format badge + name + "→ Apri" link. No inline `content` preview. Card is tolerant of missing `name`/`url`.

- [ ] **Step 1: Create `ckan-mcp-ui/components/ResourceCard.tsx`**

```tsx
import type { Resource } from "@/lib/types";

function formatBadgeColor(format: string): string {
  const f = format.toUpperCase();
  if (["CSV", "JSON", "XLSX", "XLS"].includes(f))
    return "bg-blue-100 text-blue-800";
  if (["GEOJSON", "SHP", "KML", "WMS", "GPKG"].includes(f))
    return "bg-emerald-100 text-emerald-800";
  return "bg-slate-100 text-slate-700";
}

export function ResourceCard({ resource }: { resource: Resource }) {
  const display = resource.name || resource.url || "(senza nome)";
  const badge = resource.format?.trim() ? resource.format.toUpperCase() : "—";

  return (
    <div className="flex items-center gap-3 rounded-md border border-slate-200 bg-white px-3 py-2">
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
  );
}
```

- [ ] **Step 2: Create `ckan-mcp-ui/components/ResourceList.tsx`**

```tsx
import type { Resource } from "@/lib/types";
import { ResourceCard } from "./ResourceCard";

export function ResourceList({ resources }: { resources: Resource[] }) {
  if (resources.length === 0) return null;
  return (
    <div className="mt-3 space-y-2">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
        Risorse trovate ({resources.length})
      </p>
      <div className="space-y-1.5">
        {resources.map((r, i) => (
          <ResourceCard key={`${r.url || r.name}-${i}`} resource={r} />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Typecheck**

```
npx tsc --noEmit
```
Expected: exit code 0.

- [ ] **Step 4: Commit**

```
git add ckan-mcp-ui/components/ResourceCard.tsx ckan-mcp-ui/components/ResourceList.tsx
git commit -m "feat(ui): add ResourceCard and ResourceList"
```

---

## Task 6: `Message` component

**Files:**
- Create: `ckan-mcp-ui/components/Message.tsx`

Three visual variants by `role` (per spec § 4). Splits `text` on `\n\n` for paragraphs.

- [ ] **Step 1: Create `ckan-mcp-ui/components/Message.tsx`**

```tsx
import type { ChatMessage } from "@/lib/types";
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
        <Paragraphs text={message.text} />
        <ResourceList resources={message.resources} />
        <div className="mt-3 text-xs text-slate-400">
          ⏱ {(message.durationMs / 1000).toFixed(1)}s
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

```
npx tsc --noEmit
```
Expected: exit code 0.

- [ ] **Step 3: Commit**

```
git add ckan-mcp-ui/components/Message.tsx
git commit -m "feat(ui): add Message component with user/assistant/error variants"
```

---

## Task 7: `MessageList` (scroll container + empty state)

**Files:**
- Create: `ckan-mcp-ui/components/MessageList.tsx`

Auto-scrolls to bottom on new messages. Empty state shows a short hint.

- [ ] **Step 1: Create `ckan-mcp-ui/components/MessageList.tsx`**

```tsx
"use client";

import { useEffect, useRef } from "react";
import type { ChatMessage } from "@/lib/types";
import { Message } from "./Message";

type Props = {
  messages: ChatMessage[];
  loading: boolean;
  emptyState?: React.ReactNode;
};

export function MessageList({ messages, loading, emptyState }: Props) {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, loading]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <div className="max-w-md text-center">
          {emptyState ?? (
            <p className="text-slate-500">
              Fai una domanda al portale CKAN selezionato. Puoi partire da uno
              degli esempi qui sotto.
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
      {messages.map((m, i) => (
        <Message key={i} message={m} />
      ))}
      {loading ? (
        <div className="flex justify-start">
          <div className="rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-2 text-sm text-slate-500 shadow-sm">
            <span className="inline-block animate-pulse">L'agent sta pensando…</span>
          </div>
        </div>
      ) : null}
      <div ref={bottomRef} />
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

```
npx tsc --noEmit
```
Expected: exit code 0.

- [ ] **Step 3: Commit**

```
git add ckan-mcp-ui/components/MessageList.tsx
git commit -m "feat(ui): add MessageList with auto-scroll and empty state"
```

---

## Task 8: `ChatInput` (textarea + submit)

**Files:**
- Create: `ckan-mcp-ui/components/ChatInput.tsx`

Per spec § 4: Enter submits, Shift+Enter inserts newline, disabled while loading, empty/whitespace input keeps button disabled.

- [ ] **Step 1: Create `ckan-mcp-ui/components/ChatInput.tsx`**

```tsx
"use client";

import { useState, useEffect, useRef } from "react";

type Props = {
  onSubmit: (query: string) => void;
  loading: boolean;
  prefill?: string;
  prefillKey?: number;
};

export function ChatInput({ onSubmit, loading, prefill, prefillKey }: Props) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (prefill !== undefined) {
      setValue(prefill);
      textareaRef.current?.focus();
    }
  }, [prefill, prefillKey]);

  const trimmed = value.trim();
  const canSubmit = !loading && trimmed.length > 0;

  function submit() {
    if (!canSubmit) return;
    onSubmit(trimmed);
    setValue("");
  }

  return (
    <form
      className="flex items-end gap-2 border-t border-slate-200 bg-white p-3"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        rows={2}
        disabled={loading}
        placeholder="Scrivi una domanda… (Invio per inviare, Shift+Invio per andare a capo)"
        className="flex-1 resize-none rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-slate-50"
      />
      <button
        type="submit"
        disabled={!canSubmit}
        className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:bg-slate-300"
      >
        Invia
      </button>
    </form>
  );
}
```

- [ ] **Step 2: Typecheck**

```
npx tsc --noEmit
```
Expected: exit code 0.

- [ ] **Step 3: Commit**

```
git add ckan-mcp-ui/components/ChatInput.tsx
git commit -m "feat(ui): add ChatInput with Enter-to-submit and prefill support"
```

---

## Task 9: `PortalSelect` (dropdown + custom URL field)

**Files:**
- Create: `ckan-mcp-ui/components/PortalSelect.tsx`

Per spec § 4: 5 presets + "Personalizzato…" reveals a text input. Empty custom value → caller treats it as "omit `base_url`".

- [ ] **Step 1: Create `ckan-mcp-ui/components/PortalSelect.tsx`**

```tsx
"use client";

import { useState } from "react";
import {
  PORTAL_PRESETS,
  CUSTOM_PORTAL_VALUE,
  DEFAULT_PORTAL,
} from "@/lib/portals";

type Props = {
  value: string;
  onChange: (url: string) => void;
};

export function PortalSelect({ value, onChange }: Props) {
  const isPreset = PORTAL_PRESETS.some((p) => p.url === value);
  const [mode, setMode] = useState<"preset" | "custom">(
    isPreset || value === "" ? "preset" : "custom",
  );

  function handleSelectChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const next = e.target.value;
    if (next === CUSTOM_PORTAL_VALUE) {
      setMode("custom");
      onChange("");
    } else {
      setMode("preset");
      onChange(next);
    }
  }

  const selectValue = mode === "custom" ? CUSTOM_PORTAL_VALUE : value || DEFAULT_PORTAL;

  return (
    <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
      <label className="text-xs font-medium uppercase tracking-wide text-slate-500 sm:text-sm sm:normal-case sm:tracking-normal sm:text-slate-600">
        Portale
      </label>
      <select
        value={selectValue}
        onChange={handleSelectChange}
        className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      >
        {PORTAL_PRESETS.map((p) => (
          <option key={p.url} value={p.url}>
            {p.label}
          </option>
        ))}
        <option value={CUSTOM_PORTAL_VALUE}>Personalizzato…</option>
      </select>
      {mode === "custom" ? (
        <input
          type="url"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="https://..."
          className="flex-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      ) : null}
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

```
npx tsc --noEmit
```
Expected: exit code 0.

- [ ] **Step 3: Commit**

```
git add ckan-mcp-ui/components/PortalSelect.tsx
git commit -m "feat(ui): add PortalSelect with presets and custom URL input"
```

---

## Task 10: `ChatHeader` and `ExampleQueries`

**Files:**
- Create: `ckan-mcp-ui/components/ChatHeader.tsx`
- Create: `ckan-mcp-ui/components/ExampleQueries.tsx`

- [ ] **Step 1: Create `ckan-mcp-ui/components/ChatHeader.tsx`**

```tsx
"use client";

import { PortalSelect } from "./PortalSelect";

type Props = {
  baseUrl: string;
  onBaseUrlChange: (url: string) => void;
  onReset: () => void;
  canReset: boolean;
};

export function ChatHeader({
  baseUrl,
  onBaseUrlChange,
  onReset,
  canReset,
}: Props) {
  return (
    <header className="flex flex-col gap-3 border-b border-slate-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-base font-semibold text-slate-900">
          CKAN MCP Agent — Demo
        </h1>
        <p className="text-xs text-slate-500">
          Chat stateless verso il portale CKAN selezionato.
        </p>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <PortalSelect value={baseUrl} onChange={onBaseUrlChange} />
        <button
          type="button"
          onClick={onReset}
          disabled={!canReset}
          className="rounded-md border border-slate-300 bg-white px-3 py-1 text-sm text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50"
        >
          Nuova chat
        </button>
      </div>
    </header>
  );
}
```

- [ ] **Step 2: Create `ckan-mcp-ui/components/ExampleQueries.tsx`**

```tsx
"use client";

import { EXAMPLE_QUERIES } from "@/lib/examples";

type Props = {
  onPick: (query: string) => void;
  disabled: boolean;
};

export function ExampleQueries({ onPick, disabled }: Props) {
  return (
    <div className="flex flex-wrap gap-2">
      {EXAMPLE_QUERIES.map((ex) => (
        <button
          key={ex.label}
          type="button"
          onClick={() => onPick(ex.query)}
          disabled={disabled}
          className="rounded-full border border-slate-300 bg-white px-3 py-1 text-xs text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50"
        >
          {ex.label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Typecheck**

```
npx tsc --noEmit
```
Expected: exit code 0.

- [ ] **Step 4: Commit**

```
git add ckan-mcp-ui/components/ChatHeader.tsx ckan-mcp-ui/components/ExampleQueries.tsx
git commit -m "feat(ui): add ChatHeader and ExampleQueries"
```

---

## Task 11: Wire it all together in `app/page.tsx`

**Files:**
- Modify: `ckan-mcp-ui/app/page.tsx` (overwrite the placeholder from Task 3)

Per spec § 5 (state), § 7 (data flow), § 4 (`PortalSelect` empty → omit `base_url`).

- [ ] **Step 1: Replace `ckan-mcp-ui/app/page.tsx`**

```tsx
"use client";

import { useState } from "react";
import type { ChatMessage, ChatRequest, ChatResponse } from "@/lib/types";
import { DEFAULT_PORTAL } from "@/lib/portals";
import { ChatHeader } from "@/components/ChatHeader";
import { MessageList } from "@/components/MessageList";
import { ChatInput } from "@/components/ChatInput";
import { ExampleQueries } from "@/components/ExampleQueries";

export default function Page() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [baseUrl, setBaseUrl] = useState<string>(DEFAULT_PORTAL);
  const [loading, setLoading] = useState<boolean>(false);
  const [prefill, setPrefill] = useState<string | undefined>(undefined);
  const [prefillKey, setPrefillKey] = useState<number>(0);

  function pickExample(query: string) {
    setPrefill(query);
    setPrefillKey((n) => n + 1);
  }

  async function send(query: string) {
    setMessages((prev) => [...prev, { role: "user", text: query }]);
    setLoading(true);
    const t0 = performance.now();

    const body: ChatRequest = baseUrl ? { query, base_url: baseUrl } : { query };

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const text = await res.text();
      let parsed: ChatResponse | { error: string };
      try {
        parsed = JSON.parse(text);
      } catch {
        parsed = { error: "Risposta non valida dal proxy" };
      }

      const durationMs = performance.now() - t0;

      if (!res.ok || "error" in parsed) {
        const errText =
          "error" in parsed
            ? parsed.error
            : `Errore HTTP ${res.status}`;
        setMessages((prev) => [...prev, { role: "error", text: errText }]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            text: parsed.text,
            resources: parsed.resources ?? [],
            durationMs,
          },
        ]);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setMessages((prev) => [
        ...prev,
        { role: "error", text: `Errore di rete: ${message}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-screen flex-col">
      <ChatHeader
        baseUrl={baseUrl}
        onBaseUrlChange={setBaseUrl}
        onReset={() => setMessages([])}
        canReset={messages.length > 0 && !loading}
      />
      <MessageList
        messages={messages}
        loading={loading}
        emptyState={
          <div className="space-y-3">
            <p className="text-slate-500">
              Fai una domanda al portale CKAN selezionato. Puoi partire da uno
              degli esempi:
            </p>
            <ExampleQueries onPick={pickExample} disabled={loading} />
          </div>
        }
      />
      {messages.length > 0 ? (
        <div className="border-t border-slate-200 bg-slate-50 px-4 py-2">
          <ExampleQueries onPick={pickExample} disabled={loading} />
        </div>
      ) : null}
      <ChatInput
        onSubmit={send}
        loading={loading}
        prefill={prefill}
        prefillKey={prefillKey}
      />
    </div>
  );
}
```

- [ ] **Step 2: Run `npm run dev` and exercise the UI manually**

```
npm run dev
```
With `ckan-agent` running on `:8002` (`make up` from repo root):
- Open `http://localhost:3000`.
- Verify: header, portal selector, "Nuova chat" button, empty state with example buttons, input field.
- Click an example chip → input is prefilled → press Invio → user bubble appears, then loading hint, then assistant bubble with `text` and (if any) resource cards + duration footer.
- Click "Nuova chat" → message list clears.
- Switch the portal dropdown to `data.gov.uk` → send a query → confirm the request body in DevTools Network includes `"base_url":"https://data.gov.uk"`.
- Switch to "Personalizzato…" with an empty value → confirm DevTools Network shows the request body WITHOUT `base_url`.

Stop the dev server.

- [ ] **Step 3: Typecheck**

```
npx tsc --noEmit
```
Expected: exit code 0.

- [ ] **Step 4: Lint**

```
npm run lint
```
Expected: exit code 0 (warnings acceptable; fix any errors).

- [ ] **Step 5: Commit**

```
git add ckan-mcp-ui/app/page.tsx
git commit -m "feat(ui): wire chat page state, fetch loop, and prefill flow"
```

---

## Task 12: Dockerfile and compose service

**Files:**
- Create: `ckan-mcp-ui/Dockerfile`
- Modify: `docker-compose.yml` — add `ckan-ui` service

- [ ] **Step 1: Create `ckan-mcp-ui/Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1.7

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
```

Note: there is currently no `public/` directory in `ckan-mcp-ui/`. Create it empty so the `COPY` does not fail:
```
mkdir -p ckan-mcp-ui/public
```
Then keep it tracked by adding a placeholder:
```
echo "" > ckan-mcp-ui/public/.gitkeep
```

- [ ] **Step 2: Build the Docker image standalone**

```
docker build -t ckan-mcp-ui:local ckan-mcp-ui
```
Expected: image builds successfully. If it fails on `node_modules` issues, ensure `ckan-mcp-ui/.dockerignore` from Task 1 is in place.

- [ ] **Step 3: Add the `ckan-ui` service to `docker-compose.yml`**

Open `docker-compose.yml`. Locate the `ckan-agent` service block (search for `ckan-agent:`). Immediately after the `restart: unless-stopped` line of `ckan-agent`, and **before** the top-level `volumes:` key at the bottom, append:

```yaml
  # ───── Web UI (Next.js) ─────
  ckan-ui:
    build:
      context: ./ckan-mcp-ui
      dockerfile: Dockerfile
    image: ckan-mcp-ui:local
    container_name: ckan-ui
    ports:
      - "${UI_PORT:-3000}:3000"
    environment:
      AGENT_API_URL: ${AGENT_API_URL:-http://ckan-agent:8002}
    depends_on:
      ckan-agent:
        condition: service_started
    restart: unless-stopped
```

- [ ] **Step 4: Bring the stack up and verify**

From the repo root:
```
docker compose up -d --build ckan-ui
```
Then:
```
docker compose ps
```
Expected: `ckan-ui` is `Up` and listening on `0.0.0.0:3000`.

Open `http://localhost:3000` in a browser → home page renders → an example query returns a response.

- [ ] **Step 5: Commit**

```
git add ckan-mcp-ui/Dockerfile ckan-mcp-ui/public/.gitkeep docker-compose.yml
git commit -m "feat(ui): containerize ckan-mcp-ui and add ckan-ui compose service"
```

---

## Task 13: README + documentation hooks

**Files:**
- Create: `ckan-mcp-ui/README.md`
- Modify: `README.md` (repo root) — add UI to the host endpoints table

- [ ] **Step 1: Create `ckan-mcp-ui/README.md`**

```markdown
# ckan-mcp-ui

A minimal Next.js (App Router) chat UI that demonstrates the CKAN MCP agent.
The browser talks only to a Next.js API route which proxies server-side to
`ckan-agent` (`POST /chat`). Stateless — each question is independent.

## Run with the full stack (recommended)

From the repository root:

```bash
make up
```

Then open <http://localhost:3000>.

The compose service `ckan-ui` reads `AGENT_API_URL=http://ckan-agent:8002`
from the compose environment.

## Local dev (without Docker)

Prerequisites: Node.js 20+, the `ckan-mcp-agent` running on `:8002` (e.g. via
`docker compose up ckan-agent`).

```bash
cd ckan-mcp-ui
cp .env.local.example .env.local
npm install
npm run dev
```

Open <http://localhost:3000>.

## Scripts

| Command            | What it does                          |
|--------------------|---------------------------------------|
| `npm run dev`      | Next.js dev server on `:3000`         |
| `npm run build`    | Production build (standalone output)  |
| `npm run start`    | Run the production build              |
| `npm run lint`     | `next lint`                           |
| `npm run typecheck`| `tsc --noEmit`                        |

## Smoke test (manual)

After `make up` from the repo root:

1. <http://localhost:3000> loads, header + portal selector + example chips visible.
2. Click the chip "5 dataset più recenti" → press Invio → an assistant bubble
   appears with `text` populated and a duration footer (`⏱ N.Ns`).
3. Send "Mostrami i dettagli del dataset 2908fe96-58c4-40fe-8b29-9d4d78715ba7"
   → at least one resource card is rendered with a clickable `→ Apri` link.
4. Switch portal to "data.gov.uk" → send "List recent datasets about transport"
   → confirm a different portal is answering (resources / phrasing differ).
5. `docker compose stop ckan-agent` → resend a query → red error bubble (502)
   appears → UI stays usable. Restart with `docker compose start ckan-agent`.

## Architecture

See [`docs/superpowers/specs/2026-05-24-ckan-chat-ui-design.md`](../docs/superpowers/specs/2026-05-24-ckan-chat-ui-design.md).
```

- [ ] **Step 2: Add the UI row to the host endpoints table in the root `README.md`**

Open `README.md`. Find the existing "Endpoints exposed on the host" table (search for `| Service` near "Quick start — local with Ollama"). It currently has 3 rows (CKAN MCP server, Agent API, Ollama). Add a 4th row after the Agent API row:

```
| Web UI               | `http://localhost:3000`          | Chat demo (Next.js). Talks to the agent via `/api/chat`. |
```

- [ ] **Step 3: Commit**

```
git add ckan-mcp-ui/README.md README.md
git commit -m "docs(ui): document ckan-mcp-ui and link it from the root README"
```

---

## Task 14: Final acceptance verification

This task has no code — it's the explicit gate that the spec's "Acceptance criteria" (§ 13) are met.

- [ ] **Step 1: Full stack smoke test**

From the repo root, with all services freshly rebuilt:
```
docker compose down
make up
docker compose ps
```
Expected: `ckan-ollama`, `ckan-mcp`, `ckan-agent`, `ckan-ui` all `Up`.

- [ ] **Step 2: Browser smoke test**

Open <http://localhost:3000>. Execute every step from the "Smoke test (manual)" section of `ckan-mcp-ui/README.md`. All 5 steps must pass.

- [ ] **Step 3: Static checks**

```
cd ckan-mcp-ui
npm run typecheck
npm run lint
```
Expected: both exit 0 (lint warnings are acceptable; errors are not).

- [ ] **Step 4: Confirm acceptance criteria from the spec**

Open `docs/superpowers/specs/2026-05-24-ckan-chat-ui-design.md` § 13 and confirm each of the 5 criteria is satisfied. If any is not, file a follow-up task; do not paper over.
