# Security Policy

opendata-ai integrates public-data portals, MCP servers, AI providers and optional authentication. Please report security issues privately and do not open a public GitHub issue for vulnerabilities.

## Supported versions

The `main` branch is the only supported development line unless a release branch is explicitly created.

## What to report

Please report:

- exposed secrets, tokens or credentials;
- authentication or authorization bypasses;
- server-side request forgery risks in URL fetching or public-data previews;
- unsafe file parsing, archive extraction or path traversal;
- injection risks in query building, SQL, prompts or generated metadata;
- vulnerabilities in MCP tools that could leak data or execute unintended actions;
- dependency vulnerabilities with a realistic exploit path.

## How to report

Use GitHub private vulnerability reporting if enabled for the repository. If it is not enabled, contact the maintainer privately through the contact information in the organization profile or project documentation.

Please include:

- affected component or path;
- reproduction steps;
- impact;
- suggested fix, if known;
- whether the issue is already public.

## Handling expectations

Security reports will be triaged as quickly as possible. If the issue is confirmed, the fix will be prepared before public disclosure whenever practical.

## Project-specific notes

- Never commit `.env` files, API keys, Clerk secrets, Anthropic/OpenAI keys or private portal credentials.
- Public-data URLs should be validated before fetching and should not allow access to internal network resources.
- AI summaries must not expose hidden prompts, secrets or private runtime configuration.
- Generated exports should avoid personal data unless the source is lawfully public and the user clearly requested that dataset.
