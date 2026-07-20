"""Product tools registered on the FastMCP server (issue #131).

Each tool maps one of opendata-ai's four product modes (+ classify) onto a
backend REST endpoint via ``BackendClient``. No product logic lives here — the
backend owns orchestration, LLM provider resolution, cache and fail-safe (R13:
these tools expose product capabilities to an external LLM/harness such as
OpenClaw; they do NOT reimplement them).
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .client import BackendClient, BackendError

# Search/classify are read-only & idempotent; territory/maturity persist an
# assessment/report server-side, so they are not marked idempotent.
_READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                             idempotentHint=True, openWorldHint=True)
_WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False,
                         idempotentHint=False, openWorldHint=True)


def register_tools(mcp: FastMCP) -> None:
    """Register the product tools on the given FastMCP instance."""

    @mcp.tool(annotations=_READ_ONLY)
    async def esplora_cerca_dataset(
        query: str,
        base_url: str | None = None,
        prefer_geo: bool | None = None,
    ) -> dict[str, Any]:
        """Esplora — conversational multi-source dataset search across CKAN/ISTAT/….

        Runs the backend orchestrator fan-out and returns a synthesis plus the
        resources actually found (each with a preview URL). Mirrors the product's
        "Esplora" mode.

        Args:
            query: Natural-language question (e.g. "piste ciclabili a Bologna",
                "tasso di disoccupazione 2018-2023").
            base_url: Optional CKAN portal to target (else the backend default).
            prefer_geo: Bias toward geographic resources (GeoJSON/SHP/KML) — for
                map use cases.
        """
        async with BackendClient() as c:
            return await c.search_datasets(query, base_url=base_url, prefer_geo=prefer_geo)

    @mcp.tool(annotations=_WRITE)
    async def territorio_analizza_comune(
        istat_code: str | None = None,
        nome_comune: str | None = None,
        temi: list[str] | None = None,
        anno_da: int | None = None,
        anno_a: int | None = None,
    ) -> dict[str, Any]:
        """Territorio — evidence-based report for one comune (profile, investments, gaps).

        Mirrors the product's "Territorio" mode (`POST /territory/report`). Requires
        the ISTAT code; if only the name is known, resolve it first with
        `esplora_cerca_dataset` or an ISTAT lookup — this tool does not geocode.

        Args:
            istat_code: ISTAT comune code (e.g. "072021" for Gioia del Colle).
            nome_comune: Comune name — accepted only as a hint; `istat_code` wins.
            temi: Optional list of themes to focus the report.
            anno_da: Optional start year for time-bounded sections.
            anno_a: Optional end year.
        """
        code = (istat_code or "").strip()
        if not code:
            raise BackendError(
                "Serve istat_code (codice ISTAT del comune). Il nome da solo non basta: "
                "risolvilo prima in codice ISTAT."
            )
        async with BackendClient() as c:
            return await c.territory_report(
                istat_code=code, temi=temi, anno_da=anno_da, anno_a=anno_a
            )

    @mcp.tool(annotations=_WRITE)
    async def maturita_scorecard_ente(
        entity: str,
        base_url: str | None = None,
        istat_code: str | None = None,
        comune_nome: str | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Maturità — ODM 2025 open-data maturity scorecard of an entity (4 dimensions + levers).

        Mirrors the product's "Maturità" mode (`POST /maturity/assess`).

        Args:
            entity: Entity / CKAN organisation slug (e.g. "comune-di-gioia-del-colle").
            base_url: Optional CKAN portal where the entity publishes.
            istat_code: Optional ISTAT comune code to link the entity to a comune
                (enables the value⇄maturity loop and the regional-portal fallback).
            comune_nome: Optional comune name (portal resolution).
            force: Re-run the assessment ignoring the cache.
        """
        entity = (entity or "").strip()
        if not entity:
            raise BackendError("Serve 'entity' (slug organizzazione/ente).")
        async with BackendClient() as c:
            return await c.maturity_assess(
                entity=entity, base_url=base_url, istat_code=istat_code,
                comune_nome=comune_nome, force=force,
            )

    @mcp.tool(annotations=_READ_ONLY)
    async def qualita_diagnosi_dataset(
        content: str | None = None,
        url: str | None = None,
        format: str | None = None,
    ) -> dict[str, Any]:
        """Qualità — deterministic quality diagnosis of a dataset (structure, issues, score).

        Mirrors the product's "Qualità" (Data Quality Lab) mode
        (`POST /quality/profile`). Provide either inline `content` or a public
        `url`. Deterministic: nothing is invented, only what's measurable.

        Args:
            content: Raw file content (CSV/TSV/TXT or GeoJSON).
            url: Public URL of the dataset resource (alternative to content).
            format: Optional hint ("csv"/"geojson"); auto-detected otherwise.
        """
        if not content and not url:
            raise BackendError("Serve 'content' (testo del file) oppure 'url' pubblico.")
        async with BackendClient() as c:
            return await c.quality_profile(content=content, url=url, fmt=format)

    @mcp.tool(annotations=_READ_ONLY)
    async def classifica_dataset(
        source: str,
        dataset_id: str,
        dataset_name: str,
        taxonomy: list[str],
        dataset_description: str | None = None,
    ) -> dict[str, Any]:
        """Classify a dataset against a taxonomy (0–1 score per category).

        Mirrors `POST /datasets/classify` (three-layer cache: Redis → Postgres → LLM).

        Args:
            source: Source tag (e.g. "ckan", "istat").
            dataset_id: Stable dataset identifier within the source.
            dataset_name: Dataset title.
            taxonomy: Categories to score against (e.g. ["energy","transport"]).
            dataset_description: Optional description to improve accuracy.
        """
        if not taxonomy:
            raise BackendError("Serve 'taxonomy' (lista di categorie non vuota).")
        async with BackendClient() as c:
            return await c.classify(
                source=source, dataset_id=dataset_id, dataset_name=dataset_name,
                taxonomy=taxonomy, dataset_description=dataset_description,
            )
