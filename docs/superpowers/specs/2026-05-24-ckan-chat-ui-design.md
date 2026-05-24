# CKAN Chat UI — Design

**Date:** 2026-05-24
**Status:** Approved (design phase)
**Scope:** A minimal Next.js web UI to demonstrate the `ckan-mcp-agent` + `ckan-mcp-server` stack via the existing `POST /chat` endpoint.

---

## 1. Goal

Provide a small, polished web page that lets a user:

- ask natural-language questions to the agent
- pick the target CKAN portal (`base_url`)
- see the agent's narrative answer and the resources it found
- run pre-canned example queries to demo the system without typing

The UI is a **thin client** over the existing agent HTTP API. No new business logic.

---

## 2. Architecture

New top-level package `ckan-mcp-ui/`, sibling to `ckan-mcp-server/` and `ckan-mcp-agent/`.

- **Framework:** Next.js 15 (App Router, TypeScript, `output: 'standalone'`)
- **Styling:** Tailwind CSS (no component library)
- **Pages:** one — `/`
- **Server API:** one — `app/api/chat/route.ts` (proxy to the agent)

### Request topology

```
┌──────────┐ POST /api/chat ┌────────────────┐  POST /chat   ┌──────────────┐
│ Browser  │ ──────────────▶│ Next.js server │ ─────────────▶│ ckan-agent   │
│ (React)  │ ◀──────────────│ (proxy + types)│ ◀─────────────│ :8002        │
└──────────┘                 └────────────────┘                └──────────────┘
```

The browser never talks to the agent directly. The Next.js API route forwards the request server-side. This gives:

- **no CORS** — fetch originates from the Next server
- **single source of truth for backend URL** — `AGENT_API_URL` env var on the server only
- **one place to normalize/validate** the upstream response before it reaches React

### Deployment

A new compose service `ckan-ui` is added to `docker-compose.yml`. It depends on `ckan-agent` and is exposed on host `:3000`.

```yaml
ckan-ui:
  build:
    context: ./ckan-mcp-ui
  environment:
    AGENT_API_URL: http://ckan-agent:8002
  ports: ["3000:3000"]
  depends_on:
    ckan-agent:
      condition: service_started
```

After `make up`, the user opens `http://localhost:3000`.

For local dev without Docker: `cd ckan-mcp-ui && npm install && npm run dev` (uses `.env.local` with `AGENT_API_URL=http://localhost:8002`).

---

## 3. File layout

```
ckan-mcp-ui/
├── app/
│   ├── layout.tsx          # HTML shell, fonts, <body>
│   ├── page.tsx            # chat page (client component, holds state)
│   ├── globals.css         # Tailwind directives
│   └── api/chat/route.ts   # POST proxy → AGENT_API_URL/chat
├── components/
│   ├── ChatHeader.tsx      # title + portal selector + reset button
│   ├── PortalSelect.tsx    # dropdown of presets + free-text input
│   ├── ExampleQueries.tsx  # 4–5 pre-canned query buttons
│   ├── MessageList.tsx     # scroll container, maps state to <Message>
│   ├── Message.tsx         # user/assistant bubble + duration + <ResourceList>
│   ├── ResourceList.tsx    # maps resources[] to <ResourceCard>
│   ├── ResourceCard.tsx    # format badge + name + "Open" link
│   └── ChatInput.tsx       # textarea + submit, disabled while loading
├── lib/
│   ├── types.ts            # ChatRequest, ChatResponse, Resource, ChatMessage
│   └── examples.ts         # 5 example queries (subset of requests/agent-chat.http)
├── public/
├── Dockerfile              # multi-stage Node 20 → standalone runtime
├── next.config.ts          # output: 'standalone'
├── package.json
├── tsconfig.json
└── .env.local.example
```

### Why these boundaries

- `page.tsx` owns state — small enough to live in one file (~80 lines)
- `Message.tsx` decides the visual treatment per role (user / assistant / error). It composes `ResourceList`, but doesn't know fetch logic
- `ResourceCard.tsx` is a pure presentation component — receives a `Resource`, renders a card
- `api/chat/route.ts` is the only place that knows about `AGENT_API_URL`, timeouts, and how to read the upstream body

A reader can answer "what does this do, how do I use it, what does it depend on?" for each file in under a minute.

---

## 4. Components

### `ChatHeader`
Title (`CKAN MCP Agent — Demo`), `<PortalSelect>`, "Nuova chat" button (calls `onReset`).

### `PortalSelect`
Dropdown with 5 preset portals:
- `https://www.dati.gov.it/opendata` (default)
- `https://data.gov.uk`
- `https://data.gov`
- `https://open.canada.ca/data/en`
- `https://data.gov.au`

A 6th option, "Personalizzato…", reveals a text input. The selected value populates `base_url` on the next request. If the value is an empty string (e.g. user picked "Personalizzato…" and didn't type), the request omits `base_url` so the agent falls back to its server-side `CKAN_DEFAULT_BASE_URL`.

The request builder is explicit about this:

```ts
const body: ChatRequest = baseUrl
  ? { query, base_url: baseUrl }
  : { query };
```

### `ExampleQueries`
Renders 4–5 buttons from `lib/examples.ts`. Clicking one fills the input (does not auto-send) — the user reviews and presses Invio.

Example set:
1. `"Mostrami i 5 dataset più recenti su dati.gov.it"`
2. `"List recent datasets about transport"` (with `base_url: data.gov.uk`)
3. `"Mostrami i dettagli del dataset 2908fe96-58c4-40fe-8b29-9d4d78715ba7"`
4. `"Quali organizzazioni pubblicano dati su trasporti?"`
5. `"Show CKAN portal status"`

### `MessageList`
A vertical scroll container. Auto-scrolls to bottom when a new message arrives. Empty state: shows a short hint + `<ExampleQueries>`.

### `Message`
Three visual variants by `role`:
- **user** — right-aligned bubble, blue background
- **assistant** — left-aligned bubble, white background with border. Shows `text` (rendered as paragraphs, splitting on `\n\n`), then `<ResourceList>` if `resources.length > 0`, then footer with `⏱ {durationMs/1000}s`
- **error** — left-aligned bubble, red border + red text

No markdown rendering — the agent already returns clean narrative prose. (If needed later, add `react-markdown`; not in scope now.)

### `ResourceList`
Vertical stack of `<ResourceCard>`s. Header: `Risorse trovate (${count})`.

### `ResourceCard`
- Format badge on the left (uppercase, monospace, colored by format family: blue=tabular, green=geo, gray=other)
- Resource `name` (or truncated `url` if name missing)
- Right side: `→ Apri` link that opens `url` in a new tab (`target="_blank"`, `rel="noopener"`)

Does NOT render `content` inline — that was explicitly out of scope per design discussion. The `content` field is ignored by the UI for now.

### `ChatInput`
Single-line `<textarea>` (auto-grow up to 4 rows). Submit on Enter (Shift+Enter = newline). "Invia" button on the right. Both disabled while `loading=true`. While loading, shows a small spinner under the input.

---

## 5. State

Lives entirely in `app/page.tsx`. Three `useState` hooks, no external store:

```ts
const [messages, setMessages] = useState<ChatMessage[]>([]);
const [baseUrl, setBaseUrl] = useState<string>(DEFAULT_PORTAL);
const [loading, setLoading] = useState<boolean>(false);
```

- `messages` — chronological list, mixed user/assistant/error
- `baseUrl` — current portal selection (string, never null — defaults to `dati.gov.it`)
- `loading` — true while a request is in flight; disables input

Reset: `setMessages([])`. The backend is stateless, so reset is purely cosmetic — there is no session to invalidate. The UI surfaces this implicitly (each message is independent).

---

## 6. Types (`lib/types.ts`)

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
  | { role: 'user'; text: string }
  | { role: 'assistant'; text: string; resources: Resource[]; durationMs: number }
  | { role: 'error'; text: string };
```

These mirror the agent's contract documented in `README.md` § "POST /chat response format". If the agent contract changes, this file is the canary.

---

## 7. Data flow

1. User types in `<ChatInput>` → submits.
2. `page.tsx`:
   - appends `{role:'user', text}` to `messages`
   - sets `loading=true`, records `t0 = performance.now()`
   - builds the body conditionally (`base_url` only included when non-empty — see § 4 `PortalSelect`)
   - calls `fetch('/api/chat', {method:'POST', body: JSON.stringify(body)})`
3. `app/api/chat/route.ts` (server-side):
   - reads `AGENT_API_URL` (defaults to `http://localhost:8002`)
   - forwards the JSON body to `${AGENT_API_URL}/chat`
   - uses `AbortSignal.timeout(120_000)` (Ollama local cold start can exceed 60s)
   - on 2xx: returns `await upstream.json()` with `status: 200`
   - on non-2xx or thrown: returns `{error: <human message>}` with `status: 502`
4. Client:
   - on `res.ok` → appends `{role:'assistant', text, resources, durationMs: performance.now() - t0}`
   - on `!res.ok` → appends `{role:'error', text: <body.error or "Backend non raggiungibile">}`
   - sets `loading=false`

---

## 8. Error handling

Three failure surfaces, each surfaced in-thread (the chat never crashes):

| Surface | Trigger | User sees |
|---|---|---|
| Browser → Next API | Network down, page offline | Red bubble: `Errore di rete: <message>` |
| Next API → agent | Agent down / 5xx / timeout | Red bubble: `Backend non raggiungibile (502)` or `Timeout dopo 120s` |
| Agent → MCP/LLM | Upstream error inside the agent — the agent still returns 200 with explanatory `text` | Normal assistant bubble (the agent's narrative is the message) |

Rules:

- **No automatic retry.** With local Ollama, retries mask real problems (model not pulled, GPU busy). User must click Invia again explicitly.
- **No swallow.** API route logs `console.error` with the upstream status, body excerpt (truncated to 500 chars), and stack.
- **No page crash.** Every failure path produces a renderable message — the conversation stays usable.

### Edge cases

- `resources: []` → no `<ResourceList>`, only text
- `resource.format` missing/empty → badge shows `—`
- `resource.url` missing → render the card without the `→ Apri` link (better to show the name than hide the card)
- empty/whitespace query → submit button stays disabled
- network response not JSON → caught in API route, surfaces as 502 with body excerpt in the error message

---

## 9. Configuration

### `ckan-mcp-ui/.env.local.example`

```
# URL of the ckan-mcp-agent HTTP API
# - dev (host):     http://localhost:8002
# - compose:        http://ckan-agent:8002
AGENT_API_URL=http://localhost:8002
```

### `docker-compose.yml` additions

A new service `ckan-ui` (see § 2). The existing `ckan-agent` service is unchanged.

### `Dockerfile` (multi-stage, Node 20-alpine)

```
Stage 1 (builder):  npm ci && npm run build  →  .next/standalone, .next/static, public
Stage 2 (runtime):  node 20-alpine, copy standalone output, CMD ["node", "server.js"]
```

Image stays under ~200 MB.

---

## 10. Testing

Minimal but real. No React unit tests — overhead not justified for a demo UI.

### Automated

- `npm run typecheck` (= `tsc --noEmit`) — catches contract drift with the agent. `ChatResponse` is the canary type.
- `npm run lint` (= `next lint`, default config) — catches obvious bugs.

Both runnable in CI later, but the spec does not require a CI job — manual run is enough for v1.

### Manual smoke (documented in `ckan-mcp-ui/README.md`)

1. `make up` → wait for healthy services → open `http://localhost:3000` → page renders, example queries visible.
2. Click example query `"Mostrami i 5 dataset più recenti su dati.gov.it"` → press Invio → assistant bubble appears with `text` populated and `durationMs` shown.
3. Send `"Mostrami i dettagli del dataset 2908fe96-58c4-40fe-8b29-9d4d78715ba7"` → at least one `<ResourceCard>` renders with a working `→ Apri` link.
4. `docker compose stop ckan-agent` → resend → red error bubble (502) appears → UI still accepts input.

These four checks cover: happy path, resource rendering, portal selector use, and failure mode.

### Out of scope

- Playwright / Cypress automation
- Visual regression
- A11y audit beyond semantic HTML and keyboard submit
- Streaming responses (the backend doesn't stream)
- Inline preview of CSV/JSON/GeoJSON `content` (explicit out-of-scope per design discussion)

---

## 11. Out of scope (explicit)

- Authentication / multi-user — the backend has none, the UI doesn't add any
- Conversation history persistence — backend is stateless; surface this fact, don't fake state
- Markdown rendering — agent already returns clean prose
- Resource `content` preview — would require 3 viewers (table / JSON tree / map). Card + link is enough for the demo
- Streaming / SSE — backend doesn't support it
- i18n — UI strings are Italian by default (matches the project's primary language); no toggle

---

## 12. Open questions

None at design time. All decisions confirmed in brainstorming:

- Framework: Next.js (App Router)
- Resources UI: simple cards with link (no inline preview)
- Deploy: compose service + Dockerfile
- Convenience features: portal selector, example queries, loading + duration, reset button

---

## 13. Acceptance criteria

This design is "done" when, after implementation:

1. `make up` brings up a working `http://localhost:3000` alongside the existing services.
2. A user can send a query, see a narrative response, and click through to a CKAN resource URL without leaving the demo.
3. The `base_url` selector demonstrably routes queries to different CKAN portals.
4. Stopping `ckan-agent` produces a readable error in the UI and does not crash the page.
5. `npm run typecheck && npm run lint` pass in `ckan-mcp-ui/`.
