# istat-mcp-server

A Model Context Protocol server that wraps the **ISTAT SDMX 2.1** REST API
(`https://sdmx.istat.it/SDMXWS/rest`).

Transports:

- `stdio` (default) — for local MCP hosts such as Claude Desktop
- `streamable-http` — for Docker / Azure deployment

The base URL is configurable via `ISTAT_SDMX_BASE_URL`; any SDMX 2.1 endpoint
that speaks the same REST dialect will work.

## Tools

| Tool                       | SDMX endpoint                                                  |
|----------------------------|----------------------------------------------------------------|
| `istat_list_dataflows`     | `GET /dataflow` (filtered client-side by `query`)              |
| `istat_get_dataflow`       | `GET /dataflow/{agency}/{id}/{version}?references=all`         |
| `istat_get_structure`      | `GET /datastructure/{agency}/{id}/{version}?references=children` |
| `istat_get_constraints`    | `GET /availableconstraint/{dataflowId}/all/all?mode=available` |
| `istat_get_codelist`       | `GET /codelist/{agency}/{id}/{version}`                        |
| `istat_get_concept`        | `GET /conceptscheme/{agency}/{scheme}/{version}`               |
| `istat_get_data`           | `GET /data/{dataflowId}/{key}` (CSV)                           |
| `istat_territorial_codes`  | static hierarchy over codelist `CL_ITTER107`                   |

All metadata responses come back as SDMX-JSON (`application/vnd.sdmx.structure+json`),
data responses come back as CSV (`application/vnd.sdmx.data+csv`).

## Run locally

```bash
pip install -e ".[dev]"
ISTAT_SDMX_BASE_URL=https://sdmx.istat.it/SDMXWS/rest istat-mcp-server
```

## Run in Docker

```bash
docker build -t istat-mcp-server .
docker run --rm -p 8080:8080 -e TRANSPORT=streamable-http istat-mcp-server
```
