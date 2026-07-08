# OSS impact and reuse

opendata-ai is designed as open-source civic AI infrastructure: a set of reusable services that help people find, verify, preview and reuse public data without needing to know every portal, API, format or metadata standard in advance.

## Why it matters

Public data is often technically available but practically difficult to reuse. Different public bodies publish data through different portals, APIs, formats, update cadences and metadata quality levels. opendata-ai reduces that friction by combining:

- conversational discovery across multiple open-data sources;
- deterministic resource validation to avoid invented URLs;
- map/table/chart previews for real resources;
- dataset quality checks and metadata suggestions;
- MCP servers that can be reused by other AI tools and developer workflows;
- civic reports that link claims back to public sources.

## Who benefits

- Developers who need reusable connectors for CKAN, SDMX, OpenDataSoft, Socrata and related public-data sources.
- Journalists and researchers who need citable public sources quickly.
- Public administrators and RTD/open-data managers who need to assess publication quality and maturity.
- Civic groups and citizens who need understandable, evidence-based territorial analysis.
- AI builders who need MCP servers for public-data search, fetch and verification.

## Reusable components

The repository is not only an application. Its most reusable OSS components are:

- MCP servers for open-data and public-statistics providers;
- source adapters and query fan-out logic;
- resource preview and validation utilities;
- data-quality scoring and metadata generation workflows;
- civic report/versioning patterns.

## Claude/AI relevance

Claude can help maintain and improve the project in three ways:

1. development workflow: code review, refactoring, documentation and tests;
2. product layer: safer synthesis and classification over retrieved public resources;
3. contributor experience: clearer onboarding, examples, issue triage and docs.

The project should remain useful even without a cloud AI provider. AI-generated text must be grounded in retrieved public sources, and deterministic fallbacks should expose real resources instead of hiding failures.

## Adoption goals

The next OSS goal is not only more stars. The project should become easier for external developers to reuse and contribute to. Useful indicators are:

- external issues and pull requests;
- MCP server reuse outside the main app;
- municipalities or civic groups using reports;
- documented source adapters contributed by others;
- package downloads once reusable components are published.

## Suggested Claude for OSS positioning

opendata-ai should be positioned as early-stage but serious civic infrastructure. It may not yet meet large numerical thresholds such as hundreds of dependents or many external contributors, but it is intentionally built for public reuse: open data, source-grounded AI, MCP interoperability, quality scoring and transparent civic reporting.
