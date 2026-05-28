# Use the opendata-ai MCP servers from Claude Desktop

This repo ships three FastMCP servers — `ckan-mcp-server`, `istat-mcp-server`,
and `osm-mcp`. They all support the **stdio** transport that Claude Desktop
and other MCP hosts expect, in addition to the streamable-HTTP transport used
inside the Docker stack.

Two ways to wire them up. Both work; pick the one that fits your machine.

## A. Run the published GHCR Docker images (no Python install)

This is the recommended path for users that don't want a local Python
environment. Claude Desktop pipes stdin/stdout to a container that runs the
server in stdio mode.

Add this to your `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "opendata-ckan": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "TRANSPORT=stdio",
        "-e", "CKAN_DEFAULT_BASE_URL=https://www.dati.gov.it/opendata",
        "ghcr.io/agent-engineering-studio/ckan-mcp-server:latest"
      ]
    },
    "opendata-istat": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "TRANSPORT=stdio",
        "-e", "ISTAT_SDMX_BASE_URL=https://esploradati.istat.it/SDMXWS/rest",
        "ghcr.io/agent-engineering-studio/istat-mcp-server:latest"
      ]
    },
    "opendata-osm": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "MCP_TRANSPORT=stdio",
        "ghcr.io/agent-engineering-studio/osm-mcp:latest"
      ]
    }
  }
}
```

Override `CKAN_DEFAULT_BASE_URL` per portal — the same `ckan-mcp-server`
image works against any CKAN portal (`dati.gov.it`, `data.gov.uk`,
`data.gov`, `open.canada.ca`, …).

## B. Local Python install (for development)

If you've already installed the servers with `pip install -e ".[dev]"`
inside `ckan-mcp-server/`, `istat-mcp-server/`, and `osm-mcp/`, the
console scripts on `$PATH` are enough:

```json
{
  "mcpServers": {
    "opendata-ckan": {
      "command": "/Users/<you>/.venvs/opendata-ai/bin/ckan-mcp-server",
      "env": {
        "TRANSPORT": "stdio",
        "CKAN_DEFAULT_BASE_URL": "https://www.dati.gov.it/opendata"
      }
    },
    "opendata-istat": {
      "command": "/Users/<you>/.venvs/opendata-ai/bin/istat-mcp-server",
      "env": {
        "TRANSPORT": "stdio",
        "ISTAT_SDMX_BASE_URL": "https://esploradati.istat.it/SDMXWS/rest"
      }
    },
    "opendata-osm": {
      "command": "/Users/<you>/.venvs/opendata-ai/bin/python",
      "args": ["-m", "osm_mcp.server"],
      "env": { "MCP_TRANSPORT": "stdio" }
    }
  }
}
```

Replace the path with the actual venv bin directory; Claude Desktop needs
an **absolute path** because it does not inherit your interactive shell's
`$PATH`.

## Smoke-testing the stdio transport

To confirm a server boots, pipe a single MCP `tools/list` request through
it manually:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | docker run --rm -i -e TRANSPORT=stdio \
      ghcr.io/agent-engineering-studio/ckan-mcp-server:latest
```

You should see a JSON-RPC response listing the 11 CKAN tools.

## Notes on the streamable-HTTP transport

The same images, run without `TRANSPORT=stdio`, default to streamable HTTP
on port 8080. That is what `docker-compose up` brings up for the
opendata-backend to consume internally; do **not** point Claude Desktop at
the HTTP transport — Claude Desktop only speaks stdio over MCP 1.x.
