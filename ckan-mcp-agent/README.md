# ckan-mcp-agent

> Part of the **opendata-ai** mono-repo — see the [root README](../README.md) for the full architecture and the two supported stack configurations.

[Microsoft Agent Framework](https://learn.microsoft.com/agent-framework/) agent that consumes the **ckan-mcp-server** via Streamable HTTP, letting an LLM reason over any CKAN open data portal.

Supports three LLM providers out of the box:

| `LLM_PROVIDER`   | Client                                  | Credentials                                 |
|------------------|-----------------------------------------|---------------------------------------------|
| `ollama`         | `OllamaChatClient` (local)              | none (local)                                |
| `azure_foundry`  | `FoundryChatClient`                     | `AZURE_AI_PROJECT_ENDPOINT` + `DefaultAzureCredential` |
| `claude`         | `AnthropicClient`                       | `ANTHROPIC_API_KEY`                         |

Default CKAN portal: `https://www.dati.gov.it/opendata` ([CKAN API docs](https://docs.ckan.org/en/2.8/api/index.html)).

## Usage — CLI

```bash
pip install -e ".[azure]"
ckan-agent                                      # interactive REPL
ckan-agent "List the 5 most recent datasets on https://data.gov.uk"
ckan-agent --provider azure_foundry "..."       # override provider
```

## Usage — HTTP API

```bash
ckan-agent-api
curl -X POST http://localhost:8002/chat \
  -H 'Content-Type: application/json' \
  -d '{"query": "Mostrami i dettagli del dataset 2908fe96-58c4-40fe-8b29-9d4d78715ba7"}'
```

## Architecture

```
 User ──► ckan-agent (Microsoft Agent Framework)
            │
            ├── ChatClient (Ollama/Azure AI Foundry/Claude)
            │
            └── MCPStreamableHTTPTool ──► ckan-mcp-server ──► CKAN portal
```
