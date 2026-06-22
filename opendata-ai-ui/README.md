# opendata-ai-ui

> Part of the **opendata-ai** mono-repo — see the [root README](../README.md) for the full architecture and the two supported stack configurations.

A minimal Next.js (App Router) chat UI that demonstrates the CKAN MCP agent.
The browser talks only to a Next.js API route which proxies server-side to
`ckan-agent` (`POST /chat`). Stateless — each question is independent.

## Run with the full stack (recommended)

From the repository root:

```bash
make up
```

Then open <http://localhost:3000>.

The compose service `opendata-ai-ui` reads `AGENT_API_URL=http://ckan-agent:8002`
from the compose environment.

## Local dev (without Docker)

Prerequisites: Node.js 20+, the `ckan-mcp-agent` running on `:8002` (e.g. via
`docker compose up ckan-agent`).

```bash
cd opendata-ai-ui
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

See the repo-level [`docs/architettura.md`](../docs/architettura.md) and
[`docs/data-model.md`](../docs/data-model.md).
