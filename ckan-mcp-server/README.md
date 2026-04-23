# ckan-mcp-server

MCP server exposing [CKAN Action API](https://docs.ckan.org/en/latest/api/) tools for **any** CKAN open data portal.

Built with the official [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk) (`FastMCP`). Supports both **stdio** (for local MCP hosts) and **Streamable HTTP** (for container deployment).

## Tools exposed

| Tool                       | CKAN action            |
|----------------------------|------------------------|
| `ckan_status_show`         | `status_show`          |
| `ckan_site_read`           | `site_read`            |
| `ckan_package_search`      | `package_search`       |
| `ckan_package_show`        | `package_show`         |
| `ckan_organization_list`   | `organization_list`    |
| `ckan_organization_show`   | `organization_show`    |
| `ckan_group_list`          | `group_list`           |
| `ckan_group_show`          | `group_show`           |
| `ckan_tag_list`            | `tag_list`             |
| `ckan_datastore_search`    | `datastore_search`     |
| `ckan_datastore_search_sql`| `datastore_search_sql` |

Every tool accepts an optional `base_url` argument, so a single server instance can query any CKAN portal (dati.gov.it, data.gov.uk, data.gov, open.canada.ca, etc.). When omitted, falls back to `CKAN_DEFAULT_BASE_URL`.

## Run locally (stdio)

```bash
pip install -e .
TRANSPORT=stdio ckan-mcp-server
```

Configure in Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ckan": {
      "command": "ckan-mcp-server",
      "env": { "CKAN_DEFAULT_BASE_URL": "https://www.dati.gov.it/opendata" }
    }
  }
}
```

## Run over HTTP (Docker)

```bash
docker build -t ckan-mcp-server .
docker run --rm -p 8080:8080 \
  -e CKAN_DEFAULT_BASE_URL=https://www.dati.gov.it/opendata \
  ckan-mcp-server
```

Endpoint: `http://localhost:8080/mcp`

## Environment variables

| Var                       | Default                              | Description                          |
|---------------------------|--------------------------------------|--------------------------------------|
| `TRANSPORT`               | `stdio`                              | `stdio` \| `streamable-http` \| `sse` |
| `HOST`                    | `0.0.0.0`                            | Bind address for HTTP transports     |
| `PORT`                    | `8080`                               | Port for HTTP transports             |
| `MCP_PATH`                | `/mcp`                               | Mount path for Streamable HTTP       |
| `CKAN_DEFAULT_BASE_URL`   | `https://www.dati.gov.it/opendata`   | Default portal when no `base_url`    |
| `CKAN_HTTP_TIMEOUT`       | `30`                                 | Per-request timeout in seconds       |
| `LOG_LEVEL`               | `INFO`                               | Python logging level                 |
