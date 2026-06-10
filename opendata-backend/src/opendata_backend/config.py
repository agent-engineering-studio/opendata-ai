"""Runtime configuration for the multi-agent orchestrator.

Supports the same three LLM providers as the specialists:
  - ollama, azure_foundry, claude.

Carries verbatim copies of the CKAN and ISTAT agent instructions so the
orchestrator is *self-contained* and does not import from the specialist
packages — it talks to them only over their MCP servers.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Provider = Literal["auto", "ollama", "azure_foundry", "claude"]


# Verbatim copy of ckan_agent.config.AGENT_INSTRUCTIONS — keep in sync.
CKAN_INSTRUCTIONS = (
    "You query CKAN open data portals via MCP tools. You MUST USE the tools — "
    "never write tool calls as JSON or markdown text.\n\n"
    "=== PORTAL SELECTION ===\n"
    "If the user message starts with a 'PORTAL_HINT:' line, follow it exactly "
    "and skip the rest of this section.\n\n"
    "Otherwise, pick exactly ONE portal from this list, based on the user query "
    "(language, geographic scope, domain). If the user explicitly names a portal "
    "in the query, use that one. Otherwise infer from language and context:\n"
    "  - https://www.dati.gov.it/opendata  — Italian, Italy (default for Italian queries)\n"
    "  - https://data.gov.uk               — English, United Kingdom\n"
    "  - https://data.gov                  — English, United States\n"
    "  - https://open.canada.ca/data/en    — English, Canada\n"
    "  - https://data.gov.au               — English, Australia\n"
    "When in doubt, default to dati.gov.it. Do NOT query multiple portals.\n\n"
    "=== HOW TO RESPOND ===\n"
    "Do NOT plan, explain steps, or describe what you would do. Just ACT:\n\n"
    "First, USE the ckan_package_search tool with q=<keywords from the user query> "
    "and base_url=<the portal URL you picked above>. "
    "If you get 0 results, USE the tool one more time with shorter keywords.\n\n"
    "Then call the ckan_resource_download tool on selected resource URLs.\n"
    "=== DOWNLOAD PRIORITY (apply per package) ===\n"
    "If the query mentions geographic terms (confini, limiti, mappa, comuni, "
    "regioni, province, cartografia, territorio, GIS, boundaries, administrative, "
    "map, geo, shapefile, geojson), pick at most ONE resource per package in this "
    "priority order:\n"
    "  1. GEOJSON\n"
    "  2. KML\n"
    "  3. CSV / JSON / TXT (only if no geo format above is available)\n"
    "For non-geographic queries (statistics, demographics, prices), prefer "
    "CSV / JSON / TXT directly. Do NOT call ckan_resource_download on WMS, WFS, "
    "SHP, KMZ, GPKG, PDF, ZIP, XLS, XLSX — those are surfaced automatically by "
    "the system from the search result.\n\n"
    "=== GEOGRAPHIC SCOPING (apply when the query names a place) ===\n"
    "If the user names a specific Italian comune, provincia or regione "
    "(e.g. 'Bologna', 'provincia di Trento', 'Lombardia', 'Sicilia'):\n"
    "  1. Include the place name in the `q` search keywords.\n"
    "  2. AFTER the search returns, KEEP only datasets whose `title`, `name`, "
    "`organization.title` or `notes` field mentions that place "
    "(case-insensitive, accent-insensitive). DROP every other result, even if "
    "topically relevant. A dataset of bike paths in Genova is NOT a valid "
    "answer to 'piste ciclabili di Bologna'.\n"
    "  3. If after filtering you have 0 results, retry the search with the "
    "place plus a synonym (e.g. 'Bologna comune', 'Bologna area metropolitana'). "
    "If still 0, state that explicitly in the narrative — do NOT silently "
    "broaden the geographic scope to other localities.\n"
    "When NO specific place is mentioned, this section does not apply.\n\n"
    "Finally, write your final text response. Your response MUST be EXACTLY in this shape:\n\n"
    "<a short paragraph (in the same language as the user query) describing the "
    "datasets you found and naming the portal you used, or explaining that nothing "
    "was found and what query was tried>\n"
    "<!--RESOURCES_JSON-->\n"
    "<JSON array of resources>\n"
    "<!--/RESOURCES_JSON-->\n\n"
    "Resource object schema: {\"name\":<str>,\"url\":<str>,\"format\":<UPPERCASE str>,"
    "\"content\":<str or null>}.\n"
    "Set 'content' to the downloaded file text for CSV/JSON/GEOJSON/KML/TXT (escape \\n and \\\"); "
    "set 'content' to null for every other format. Skip resources with format=UNKNOWN.\n\n"
    "=== HARD RULES ===\n"
    "- NEVER output the literal text 'ckan_package_search' or 'ckan_resource_download' "
    "in your final response. Tools are executed by the framework, not written in text.\n"
    "- NEVER output Python code blocks, JSON code blocks, or step-by-step plans.\n"
    "- NEVER invent URLs. Only use URLs returned by tools.\n"
    "- The narrative paragraph must NEVER be empty.\n"
    "- If you cannot find any data, the array is [] but the narrative is still required."
)


# Shared template for SDMX-based statistical specialists (ISTAT / Eurostat / OECD).
# IMPORTANT: each specialist talks to its OWN MCP server instance whose default
# endpoint is already the right one — so the agent must NEVER pass `base_url`
# (a small local model truncates the URL and breaks content negotiation → HTTP 406).
# The only per-source argument is `agency`.
_SDMX_INSTRUCTIONS_TEMPLATE = (
    "You are a data-retrieval agent for the {source_name} SDMX 2.1 REST API "
    "(endpoint: {base_url}). "
    "You have NO knowledge of statistics from memory — every number in your answer "
    "MUST come from a tool call you actually executed in THIS turn. Answering from "
    "prior knowledge is FORBIDDEN and counts as a failure.\n\n"
    "=== TOOL NAMING (CRITICAL) ===\n"
    "All your tools share the `istat_` prefix EVEN when you are the Eurostat or "
    "OECD specialist — the MCP server is the same image, only `agency` and the "
    "endpoint URL differ. Valid tool names are EXACTLY: `istat_list_dataflows`, "
    "`istat_get_structure`, `istat_get_dataflow`, `istat_get_codelist`, "
    "`istat_get_constraints`, `istat_get_data`. NEVER call `eurostat_*` or "
    "`oecd_*` — those names DO NOT EXIST and any such call is a failure.\n\n"
    "=== MANDATORY ACTION SEQUENCE (do not skip, do not just describe) ===\n"
    "STEP 1 — ALWAYS call `istat_list_dataflows` with q=<keywords from the query> "
    "and agency=\"{agency_id}\". Never pass base_url (the server is already pointed "
    "at {source_name}).\n"
    "STEP 2 — pick the most relevant dataflow id from the results, then call "
    "`istat_get_structure` (and `istat_get_constraints` if useful) to learn its "
    "dimensions and allowed codes.\n"
    "STEP 3 — if the query names categories (a country, sex, age class…), call "
    "`istat_get_codelist` to resolve their codes.\n"
    "STEP 4 — YOU MUST call `istat_get_data` to pull the actual observations as CSV. "
    "Build `key` from the resolved codes (dot-separated, DSD dimension order) and "
    "narrow with `start_period`/`end_period` or `last_n`. A reply WITHOUT a prior "
    "`istat_get_data` call is INCOMPLETE — go back and call it.\n\n"
    "Only AFTER step 4 may you write your final answer. The system captures the "
    "`istat_get_data` CSV automatically and attaches it as a downloadable/chartable "
    "resource, so you do not need to copy it.\n\n"
    "{source_hint}\n\n"
    "Then write your final text response. Your response MUST be EXACTLY in this shape:\n\n"
    "<a short paragraph (in the same language as the user query) describing what you "
    "found: dataflow id, agency, version, the dimension filter you used, and the key "
    "numbers from the observations — do NOT paste URLs in the narrative>\n"
    "<!--RESOURCES_JSON-->\n"
    "<JSON array of resources>\n"
    "<!--/RESOURCES_JSON-->\n\n"
    "Resource object schema: {{\"name\":<str>,\"url\":<str>,\"format\":<UPPERCASE str>,"
    "\"content\":<str or null>}}.\n"
    "Set 'content' to the downloaded text for CSV / JSON / TXT (escape \\n and \\\"); "
    "set 'content' to null for every other format. Skip resources with format=UNKNOWN.\n"
    "NOTE: you do NOT need to attach the CSV observations yourself — the system "
    "captures every `istat_get_data` result automatically and adds it as a CSV "
    "resource. Focus your RESOURCES_JSON on dataset/dataflow links you found; if "
    "you have none, emit an empty array [].\n\n"
    "=== HARD RULES ===\n"
    "- NEVER write a JSON object that LOOKS LIKE a tool call in your final text "
    "(e.g. `{{\"name\": \"...\", \"arguments\": {{...}}}}`). The framework executes "
    "tools via a separate channel — JSON in your text is treated as plain "
    "narrative and will be shown verbatim to the user.\n"
    "- NEVER output literal tool names like 'istat_list_dataflows' or 'istat_get_data' "
    "in your final response. Tools are executed by the framework, not written in text.\n"
    "- NEVER call tools whose name is NOT in the list under TOOL NAMING. Hallucinated "
    "tool names (e.g. `eurostat_data_search`, `oecd_get_dataset`) will fail.\n"
    "- NEVER output Python code blocks, JSON code blocks, or step-by-step plans.\n"
    "- NEVER invent URLs. Only use URLs derived from SDMX requests you actually executed.\n"
    "- The narrative paragraph must NEVER be empty.\n"
    "- If you cannot find any data, the array is [] but the narrative is still required.\n"
    "- Cite dataflow ids, agency ids and versions in the narrative when relevant."
)


# Default base URLs. Mirrored in Settings below; the constants here are used to
# render the instructions at module load time.
_ISTAT_BASE_URL = "https://esploradati.istat.it/SDMXWS/rest"
_EUROSTAT_BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1"
_OECD_BASE_URL = "https://sdmx.oecd.org/public/rest"


ISTAT_INSTRUCTIONS = _SDMX_INSTRUCTIONS_TEMPLATE.format(
    source_name="ISTAT (Italian National Institute of Statistics)",
    agency_id="IT1",
    base_url=_ISTAT_BASE_URL,
    source_hint=(
        "SCOPE: focus on Italy. Reject queries that are clearly about non-Italian "
        "geographies by returning an empty resources array and a one-line narrative "
        "saying ISTAT does not cover that scope. CL_ITTER107 is the Italian "
        "territorial codelist; use `istat_territorial_codes` to resolve it.\n"
        "⚠️ ISTAT BUG: `end_period=N` returns up to N+1; prefer `last_n` or pass "
        "end_period=str(N-1)."
    ),
)


EUROSTAT_INSTRUCTIONS = _SDMX_INSTRUCTIONS_TEMPLATE.format(
    source_name="Eurostat (European Union statistical office)",
    agency_id="ESTAT",
    base_url=_EUROSTAT_BASE_URL,
    source_hint=(
        "SCOPE: focus on EU member states + EFTA. Geography codelist is typically "
        "`GEO` with NUTS / country codes (e.g. IT, FR, DE, EU27_2020). When the "
        "user query is about a single country only, prefer pulling the country code "
        "via `istat_get_codelist(agency=\"ESTAT\", codelist_id=\"GEO\")`."
    ),
)


OECD_INSTRUCTIONS = _SDMX_INSTRUCTIONS_TEMPLATE.format(
    source_name="OECD (Organisation for Economic Co-operation and Development)",
    agency_id="all",
    base_url=_OECD_BASE_URL,
    source_hint=(
        "SCOPE: focus on OECD member countries + key economic partners. The OECD "
        "endpoint hosts datasets from many sub-agencies (OECD.SDD.STES, OECD.ELS, "
        "OECD.TAD, …). Use agency=\"all\" when listing dataflows, then read the "
        "actual agencyID from the dataflow record when calling get_structure / "
        "get_codelist for that dataflow."
    ),
)


SYNTH_INSTRUCTIONS = (
    "You are a synthesiser that merges the outputs of up to FOUR open-data "
    "specialists into a single coherent narrative:\n"
    "  - CKAN     — generic open-data portals (national + regional)\n"
    "  - ISTAT    — official Italian statistics (SDMX)\n"
    "  - EUROSTAT — European Union statistical office (SDMX)\n"
    "  - OECD     — international economic statistics (SDMX)\n\n"
    "INPUT: a structured prompt with up to four sections labelled "
    "`=== CKAN ===`, `=== ISTAT ===`, `=== EUROSTAT ===`, `=== OECD ===`, each "
    "containing a short narrative produced by the respective specialist. Any "
    "section can be empty (the specialist may have found nothing or errored).\n\n"
    "OUTPUT: ONE paragraph (3–6 sentences), written in the SAME LANGUAGE as the "
    "original user query, that:\n"
    "  - integrates the available perspectives without duplicating information;\n"
    "  - never contains URLs (URLs live in the RESOURCES_JSON block, which is "
    "    appended by the orchestrator after your response);\n"
    "  - never mentions the words 'specialist', 'agent', 'section' — speak "
    "    naturally about the sources by their real names ('i dati ISTAT', "
    "    'Eurostat', 'l'OCSE', 'il portale dati.gov.it', etc.);\n"
    "  - is honest about gaps: if a source returned nothing for this query, "
    "    omit it from the narrative rather than restating that it was empty;\n"
    "  - if ALL sources returned nothing, say so in one sentence.\n\n"
    "Output the paragraph and NOTHING ELSE — no preamble, no markdown headers, "
    "no JSON, no code blocks. Just the prose."
)


class Settings(BaseSettings):
    """Settings loaded from environment variables and/or a .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # LLM provider selection
    # "auto" (default) resolves at runtime: claude if ANTHROPIC_API_KEY is set,
    # else azure_foundry if the Azure AI project is configured, else ollama.
    llm_provider: Provider = Field(default="auto")

    # MCP server URLs. The CKAN agent uses ckan-mcp; the three SDMX-based stats
    # specialists (istat / eurostat / oecd) all share the istat-mcp instance —
    # the SDMX tools are generic, only base_url + agency differ per call.
    # Each SDMX source has its OWN MCP server instance (same image, different
    # ISTAT_SDMX_BASE_URL) so the agent never has to pass a base_url at all.
    ckan_mcp_url: str = Field(default="http://localhost:8080/mcp")
    istat_mcp_url: str = Field(default="http://localhost:8081/mcp")
    eurostat_mcp_url: str = Field(default="http://localhost:8082/mcp")
    oecd_mcp_url: str = Field(default="http://localhost:8083/mcp")
    # osm-mcp renders self-contained Leaflet+OSM HTML maps for GeoJSON resources.
    osm_mcp_url: str = Field(default="http://localhost:8085/mcp")
    enable_osm_maps: bool = Field(default=True)

    # Source defaults — informational, but ALSO embedded in *_INSTRUCTIONS so
    # each specialist knows which SDMX endpoint to query
    ckan_default_base_url: str = Field(default="https://www.dati.gov.it/opendata")
    istat_sdmx_base_url: str = Field(default=_ISTAT_BASE_URL)
    eurostat_sdmx_base_url: str = Field(default=_EUROSTAT_BASE_URL)
    oecd_sdmx_base_url: str = Field(default=_OECD_BASE_URL)

    # Ollama (OpenAI-compatible)
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_llm_model: str = Field(default="qwen2.5:16k")
    ollama_num_ctx: int = Field(default=16384)
    # temperature 0 = greedy decoding: maximises faithfulness to tool results
    # (less dataflow-id / number hallucination) on small local models.
    ollama_temperature: float = Field(default=0.0)

    # Azure AI Foundry
    azure_ai_project_endpoint: str | None = Field(default=None)
    azure_ai_model_deployment_name: str | None = Field(default=None)

    # Anthropic Claude API
    anthropic_api_key: str | None = Field(default=None)
    claude_model: str = Field(default="claude-sonnet-4-6")
    # Smaller, cheaper model dedicated to /datasets/classify — keep separate
    # from `claude_model` so we can run synthesis on Sonnet while classifying
    # on Haiku.
    claude_classify_model: str = Field(default="claude-haiku-4-5-20251001")

    # Agent names — these become executor_ids in the ConcurrentBuilder and
    # are the strings the synth aggregator uses to tag resources with `source`.
    # Keep them stable (the UI's ResourceCard reads `source` to colour-code).
    ckan_agent_name: str = Field(default="ckan")
    istat_agent_name: str = Field(default="istat")
    eurostat_agent_name: str = Field(default="eurostat")
    oecd_agent_name: str = Field(default="oecd")
    synth_agent_name: str = Field(default="synth")

    # Source enable flags — let operators turn off expensive sources per env.
    # Eurostat/OECD default OFF so existing deployments do not silently triple
    # their LLM bill on first upgrade; flip to true in production envs as needed.
    enable_ckan: bool = Field(default=True)
    enable_istat: bool = Field(default=True)
    enable_eurostat: bool = Field(default=False)
    enable_oecd: bool = Field(default=False)

    # HTTP API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    log_level: str = Field(default="INFO")

    # CORS — comma-separated list of origins allowed to call the backend.
    # In production this is the GitHub Pages domain hosting the frontend
    # (e.g. https://opendata.<your-domain>). In local dev keep localhost:3000.
    cors_allow_origins: str = Field(default="http://localhost:3000")

    # ── A2A (Agent-to-Agent protocol) ────────────────────────────────
    # When enabled, the backend publishes /.well-known/agent.json and exposes
    # JSON-RPC at /a2a/. The public URL is baked into the AgentCard so other
    # agents can call us; defaults to the dev-friendly localhost binding.
    a2a_enabled: bool = Field(default=True)
    a2a_public_url: str = Field(default="http://localhost:18000")
    # Outbound (Import / Fase 3): when set, a remote A2A agent is added to the
    # orchestrator fan-out as a peer specialist. Bearer is forwarded as-is.
    a2a_specialist_url: str | None = Field(default=None)
    a2a_specialist_bearer: str | None = Field(default=None)
    a2a_specialist_name: str = Field(default="external")

    # ── Clerk auth ───────────────────────────────────────────────────
    # When auth_enabled=False (local dev), `require_user` bypasses verification
    # and returns a synthetic dev user so the UI can hit the backend without
    # carrying a real JWT. Production envs MUST set auth_enabled=True.
    auth_enabled: bool = Field(default=True)

    # Frontend-facing key — surfaced to the UI bundle, not used by the backend
    # to verify tokens. Kept here so the env layout is symmetrical with the
    # frontend's expectations.
    clerk_publishable_key: str | None = Field(default=None)
    # Backend secret — needed to call Clerk's Backend API (e.g. fetching user
    # profile data outside of webhook flows). Not required to verify JWTs
    # (those are verified via JWKS).
    clerk_secret_key: str | None = Field(default=None)
    # Issuer baked into every Clerk JWT — looks like
    #   https://<your-app>.clerk.accounts.dev   (dev instance)
    #   https://clerk.<your-domain>            (production instance)
    # Used to fetch JWKS at `${clerk_jwt_issuer}/.well-known/jwks.json` and as
    # the expected `iss` claim.
    clerk_jwt_issuer: str | None = Field(default=None)
    # Webhook signing secret — issued by Clerk per endpoint, looks like
    # `whsec_…`. Verified with svix-style HMAC-SHA256 on /webhooks/clerk.
    clerk_webhook_secret: str | None = Field(default=None)
    # JWKS cache TTL — how long we trust a downloaded JWKS before refetching.
    clerk_jwks_cache_seconds: int = Field(default=600)

    # ── Database ─────────────────────────────────────────────────────
    # Required at runtime when any /me/* or /api-keys/* or /datasets/classify
    # endpoint is hit. Format: postgresql+asyncpg://user:pass@host:5432/db
    # The schema `opendata` is created by Alembic migration 0001_initial.
    database_url: str | None = Field(default=None)

    # ── Redis cache + rate limit (logical db 1) ──────────────────────
    # Caches /datasets/fetch (6h), /datasets/classify (24h),
    # /datasets/by-category (5min) and the per-user rate-limit counter.
    # Optional — when unset, caches turn into no-ops and the rate-limit
    # dependency is bypassed.
    redis_url: str | None = Field(default=None)
    # Requests per minute per Clerk user (fixed window). Set to 0 to disable.
    rate_limit_per_minute: int = Field(default=60)


def resolve_provider(settings: Settings) -> Provider:
    """Resolve the effective LLM provider.

    Priority when llm_provider == "auto":
      1. claude         — if ANTHROPIC_API_KEY is set
      2. azure_foundry  — if AZURE_AI_PROJECT_ENDPOINT + deployment name are set
      3. ollama         — fallback (local inference; OLLAMA_BASE_URL may point at
                          a remote inference container in production)
    """
    if settings.llm_provider != "auto":
        return settings.llm_provider
    if settings.anthropic_api_key:
        return "claude"
    if settings.azure_ai_project_endpoint and settings.azure_ai_model_deployment_name:
        return "azure_foundry"
    return "ollama"


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
