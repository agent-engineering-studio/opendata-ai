# ckan-mcp-agent

[Microsoft Agent Framework](https://learn.microsoft.com/agent-framework/) agent that consumes the **ckan-mcp-server** via Streamable HTTP, letting an LLM reason over any CKAN open data portal.

Supports three LLM providers out of the box:

| `LLM_PROVIDER`  | Client                                  | Credentials                                 |
|-----------------|-----------------------------------------|---------------------------------------------|
| `ollama`        | `OpenAIChatClient` on Ollama `/v1`      | none (local)                                |
| `openai`        | `OpenAIChatClient`                      | `OPENAI_API_KEY`                            |
| `azure_openai`  | `AzureOpenAIChatClient`                 | `AZURE_OPENAI_ENDPOINT` + key or `DefaultAzureCredential` |

## Usage — CLI

```bash
pip install -e ".[azure]"
ckan-agent                                      # interactive REPL
ckan-agent "List the 5 most recent datasets on https://data.gov.uk"
ckan-agent --provider azure_openai "..."        # override provider
```

## Usage — HTTP API

```bash
ckan-agent-api
curl -X POST http://localhost:8002/chat \
  -H 'Content-Type: application/json' \
  -d '{"query": "Find air-quality datasets", "base_url": "https://www.dati.gov.it/opendata"}'
```

## Architecture

```
 User ──► ckan-agent (Microsoft Agent Framework)
            │
            ├── ChatClient (Ollama/OpenAI/Azure OpenAI)
            │
            └── MCPStreamableHTTPTool ──► ckan-mcp-server ──► CKAN portal
```
