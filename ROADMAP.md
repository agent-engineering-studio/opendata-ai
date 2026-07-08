# Roadmap

This roadmap turns opendata-ai into a clearer, easier-to-contribute open-source project. It is intentionally practical: each milestone should produce something useful for users and contributors.

## Near term

- Add reliable setup instructions for each component: backend, frontend and every MCP server.
- Add `good first issue` tasks for documentation, tests, examples and data-source adapters.
- Publish example queries for CKAN, ISTAT, Eurostat, OECD, OpenDataSoft and Socrata.
- Add regression tests for URL validation, resource previews and anti-hallucination guardrails.
- Improve the public demo documentation with screenshots and a short walkthrough.

## OSS readiness

- Keep `CONTRIBUTING.md`, `SECURITY.md`, issue templates and PR templates up to date.
- Document which components are reusable as standalone packages or MCP servers.
- Add clear labels: `good first issue`, `help wanted`, `documentation`, `data-source`, `frontend`, `backend`, `mcp`, `security`.
- Track external contributions and credit contributors in release notes.

## Reusable packages

Potential packages to extract and publish:

- `opendata-mcp-server`: common MCP server utilities and shared schemas.
- `ckan-mcp-server`: reusable CKAN Action API server.
- `istat-sdmx-mcp-server`: SDMX discovery and observation tools for ISTAT/Eurostat/OECD.
- `opendata-quality`: dataset profiling, quality scoring and metadata generation utilities.

## Civic impact

- Add public case studies for municipalities and civic groups.
- Provide examples for Responsabili per la Transizione Digitale, journalists, developers and researchers.
- Produce reproducible reports that link every claim to public data.
- Make the platform useful even when an AI provider is unavailable, through deterministic fallbacks.

## Long term

- Versioned civic reports with diffs over time.
- More official catalog standards and validators.
- Community-maintained source adapters.
- Benchmarks for data discovery quality and hallucination avoidance.
- Public dashboard showing source coverage, broken resources and dataset freshness.
