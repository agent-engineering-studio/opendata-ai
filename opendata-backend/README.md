# opendata-backend

Unified FastAPI service that absorbs the multi-source orchestrator (CKAN +
ISTAT + Eurostat + OECD) and the former specialist agents into a single
process. It is the one HTTP entry point the frontend talks to.

## Endpoints

| Method | Path | Auth | Status |
|---|---|---|---|
| GET | `/health` | public | ✅ |
| POST | `/chat` | public (today) | ✅ back-compat for the current UI |
| POST | `/datasets/search` | public (today) | ✅ multi-source fan-out |
| POST | `/datasets/by-category` | public (today) | ✅ search + category hint |
| POST | `/datasets/fetch` | public (today) | ✅ direct resource download via opendata-core |
| POST | `/datasets/classify` | public (today) | 🟡 stub (step 6, Claude Haiku 4.5) |
| POST | `/me/favorites` | public (today) | 🟡 stub (step 4 — Postgres) |
| GET  | `/me/favorites` | public (today) | 🟡 stub |
| GET  | `/me/history` | public (today) | 🟡 stub |
| POST | `/api-keys/generate` | public (today) | 🟡 stub |
| POST | `/webhooks/clerk` | public (svix-signed in step 3) | 🟡 stub |

"public (today)" means Clerk auth is wired up in step 3; until then the
endpoints are unauthenticated for local dev.

## Run locally

```bash
cd opendata-backend
pip install --pre -e ".[dev,claude]"
LLM_PROVIDER=claude ANTHROPIC_API_KEY=... opendata-backend-api
# -> http://localhost:8000
```

In Docker the build context is the repo root so the shared `opendata-core`
package is copied in alongside this service's sources.
