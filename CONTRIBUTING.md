# Contributing to opendata-ai

Thanks for helping improve opendata-ai. The goal of the project is to make public data easier to find, understand, verify and reuse through open-source AI, MCP servers and civic data workflows.

## Good first contributions

You do not need to understand the whole platform to contribute. Good entry points are:

- add or improve documentation for one MCP server;
- add tests for an existing parser, connector or quality check;
- improve examples for a CKAN, ISTAT, Eurostat, OECD or OpenDataSoft use case;
- add a new public data portal to the default source list;
- improve accessibility, labels or empty states in the frontend;
- reproduce and document a broken dataset/resource case.

Look for issues labelled `good first issue`, `documentation`, `help wanted` or `data-source`.

## Development principles

- Evidence first: answers must point to real public resources, not invented URLs.
- Fail safe: when data is missing or unreliable, the system should say so clearly.
- Reusable components: MCP servers and connectors should be useful outside the main app.
- Public-sector friendly: prefer simple setup, transparent logic and standards such as DCAT-AP_IT, FAIR and high-value datasets.
- Privacy by default: do not commit secrets, tokens, private exports or personal data.

## Suggested workflow

1. Open or comment on an issue before making a large change.
2. Fork the repository or create a feature branch.
3. Keep the change focused and small enough to review.
4. Add or update tests/docs when behavior changes.
5. Open a pull request using the PR template.

## Local setup

The repository contains several backend/frontend/MCP components. Start from the README of the component you want to modify. For documentation-only changes, no local runtime is required.

For backend changes, use the smallest runnable scope possible, for example a single MCP server or connector test rather than the whole platform.

## Pull request checklist

Before opening a PR, please check:

- [ ] the change is focused and explained clearly;
- [ ] documentation was updated where needed;
- [ ] tests or manual verification notes are included;
- [ ] no secrets, private data or generated large files were committed;
- [ ] public-data claims are linked to their source.

## Reporting problems

When reporting a bug, include:

- the public data source or portal involved;
- the exact query or endpoint used;
- expected vs actual behavior;
- logs, screenshots or response snippets when useful;
- whether the issue affects data discovery, preview, mapping, quality scoring or export.
