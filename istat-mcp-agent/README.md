# istat-mcp-agent

A Microsoft Agent Framework agent (Python) that talks to the
[`istat-mcp-server`](../istat-mcp-server) and answers natural-language
questions about ISTAT statistics.

Two entry points:

- `istat-agent` — interactive CLI (rich-powered)
- `istat-agent-api` — FastAPI service with `GET /health` and `POST /chat`

LLM providers (pick via `LLM_PROVIDER`):

- `ollama` — talk to a local Ollama daemon via its OpenAI-compatible API
- `openai` — vanilla OpenAI
- `azure_openai` — Azure OpenAI Service (API key or `DefaultAzureCredential`)

## Run locally

```bash
pip install --pre -e ".[dev,azure]"
LLM_PROVIDER=ollama istat-agent
```

## Run in Docker

```bash
docker build -t istat-mcp-agent .
docker run --rm -p 8002:8002 \
  -e LLM_PROVIDER=ollama \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -e MCP_SERVER_URL=http://host.docker.internal:8080/mcp \
  istat-mcp-agent
```
