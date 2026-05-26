# opendata-orchestrator

Multi-agent orchestrator that fans out a user query in parallel to the **CKAN**
and **ISTAT** specialists and synthesises a single answer that preserves the
`narrative + <!--RESOURCES_JSON-->` contract consumed by `opendata-ai-ui`.

Implemented with `agent_framework.orchestrations.ConcurrentBuilder` and a custom
synthesizer aggregator (see `src/orchestrator/synth.py`).

## Run standalone

```bash
pip install --pre -e ".[dev,claude]"   # or [azure]
opendata-orchestrator-api              # FastAPI on :8000
opendata-agent "trova dati su popolazione Toscana 2023"
```

The orchestrator expects both MCP servers reachable:

- `CKAN_MCP_URL` (default `http://localhost:8080/mcp`)
- `ISTAT_MCP_URL` (default `http://localhost:8081/mcp`)
