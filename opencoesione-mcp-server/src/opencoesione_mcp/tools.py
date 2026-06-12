"""OpenCoesione tool implementations registered on the FastMCP server.

All tools are thin wrappers over ``opendata_core.opencoesione.OpenCoesioneClient``
and return structured dicts (like the other MCP servers in this repo). Every
result carries:
  - ``source_url`` — the resolvable API URL of that exact response (the
    deterministic citation hook for the orchestrator's resource capture);
  - ``sources`` — a block with URL + extraction date + licence (CC BY-SA 3.0).

Territorial scoping accepts ISTAT codes (cod_comune / cod_provincia /
cod_regione) which the client resolves to OpenCoesione slugs via /territori,
or an explicit ``territorio`` slug (e.g. "bari-comune").
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from opendata_core.opencoesione import OpenCoesioneClient
from opendata_core.opencoesione.mapping import (
    CICLI,
    LICENZA_API,
    LICENZA_BULK,
    NATURE,
    STATI,
    TEMI,
)

from . import local_db

_BULK_DATASET_URL = "https://opencoesione.gov.it/it/opendata/"

_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)

#: Cap the serialized size of list payloads to stay within LLM context budgets.
_MAX_RESULTS = 50


def _with_sources(payload: dict[str, Any], *urls: str | None) -> dict[str, Any]:
    """Attach the standard `sources` block (URL + extraction date + licence)."""
    seen: list[str] = []
    for u in urls:
        if u and u not in seen:
            seen.append(u)
    payload["sources"] = [
        {"url": u, "estratto_il": date.today().isoformat(), "licenza": LICENZA_API}
        for u in seen
    ]
    return payload


def register_tools(mcp: FastMCP) -> None:
    """Register all OpenCoesione tools on the given FastMCP instance."""

    @mcp.tool(annotations=_READ_ONLY)
    async def opencoesione_search_projects(
        cod_comune: str | None = None,
        cod_provincia: str | None = None,
        cod_regione: str | None = None,
        territorio: str | None = None,
        tema: str | None = None,
        natura: str | None = None,
        stato: str | None = None,
        ciclo: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search Italian cohesion-policy funded projects, filterable by territory and theme.

        Returns slim project records (CLP, title, theme, state, funding, payments)
        plus `total`, `has_more`, `next_offset` for pagination and facet counts.

        Args:
            cod_comune: ISTAT comune code (e.g. "072006" for Bari). Resolved internally.
            cod_provincia: ISTAT province code (e.g. "072").
            cod_regione: ISTAT region code (e.g. "16" for Puglia).
            territorio: Explicit OpenCoesione territory slug (e.g. "bari-comune") —
                alternative to the ISTAT codes above.
            tema: Theme slug, one of: ricerca-e-innovazione, reti-servizi-digitali,
                competitivita-imprese, energia, ambiente, cultura-e-turismo, trasporti,
                occupazione, inclusione-sociale, istruzione, capacita-amministrativa.
            natura: Nature slug (e.g. "infrastrutture", "incentivi-alle-imprese").
            stato: Project state: non_avviato | in_corso | liquidato | concluso.
            ciclo: Programming cycle: 2000-2006 | 2007-2013 | 2014-2020 | 2021-2027.
            limit: Max results per page (default 20, hard-capped at 50).
            offset: Pagination offset — must be a multiple of `limit`.
        """
        limit = max(1, min(int(limit), _MAX_RESULTS))
        async with OpenCoesioneClient() as c:
            out = await c.search_projects(
                cod_comune=cod_comune,
                cod_provincia=cod_provincia,
                cod_regione=cod_regione,
                territorio=territorio,
                tema=tema,
                natura=natura,
                stato=stato,
                ciclo=ciclo,
                limit=limit,
                offset=offset,
            )
        return _with_sources(out, out.get("source_url"))

    @mcp.tool(annotations=_READ_ONLY)
    async def opencoesione_get_project(clp: str) -> dict[str, Any]:
        """Full detail of one funded project by its CLP (codice locale progetto).

        Includes the complete financial breakdown (EU/state/region funding, net
        amounts, commitments, payments), CUP classification, timeline dates and
        current implementation phase.

        Args:
            clp: Codice locale progetto, as returned by opencoesione_search_projects
                (e.g. "4MTRA111102"). Case-insensitive.
        """
        async with OpenCoesioneClient() as c:
            out = await c.get_project(clp)
        return _with_sources(out, out.get("source_url"))

    @mcp.tool(annotations=_READ_ONLY)
    async def opencoesione_territorial_aggregates(
        cod_comune: str | None = None,
        cod_provincia: str | None = None,
        cod_regione: str | None = None,
        territorio: str | None = None,
        ciclo: str | None = None,
    ) -> dict[str, Any]:
        """Aggregate public cost / payments / project counts for a territory.

        Returns territory-wide totals broken down by project state, theme,
        nature and year, plus context (population). Ideal for "how much funding
        landed here and on what" questions without paginating projects.

        Args:
            cod_comune: ISTAT comune code (e.g. "072006").
            cod_provincia: ISTAT province code.
            cod_regione: ISTAT region code.
            territorio: Explicit territory slug (alternative to ISTAT codes).
            ciclo: Optional programming cycle filter (e.g. "2014-2020").
        """
        async with OpenCoesioneClient() as c:
            out = await c.territorial_aggregates(
                cod_comune=cod_comune,
                cod_provincia=cod_provincia,
                cod_regione=cod_regione,
                territorio=territorio,
                ciclo=ciclo,
            )
        return _with_sources(out, out.get("source_url"))

    @mcp.tool(annotations=_READ_ONLY)
    async def opencoesione_search_soggetti(
        cod_comune: str | None = None,
        cod_provincia: str | None = None,
        cod_regione: str | None = None,
        territorio: str | None = None,
        ruolo: str | None = None,
        tema: str | None = None,
        natura: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search the bodies involved in funded projects (programmers, implementers…).

        Note: the API does NOT support free-text name search — filter by
        territory, role, theme or nature and read the `denominazione` field.

        Args:
            cod_comune: ISTAT comune code (resolved to the territory slug).
            cod_provincia: ISTAT province code.
            cod_regione: ISTAT region code.
            territorio: Explicit territory slug.
            ruolo: Role filter: programmatore | attuatore | beneficiario | realizzatore.
            tema: Theme slug (same values as opencoesione_search_projects).
            natura: Nature slug.
            limit: Max results per page (default 20, hard-capped at 50).
            offset: Pagination offset — must be a multiple of `limit`.
        """
        limit = max(1, min(int(limit), _MAX_RESULTS))
        async with OpenCoesioneClient() as c:
            out = await c.search_soggetti(
                cod_comune=cod_comune,
                cod_provincia=cod_provincia,
                cod_regione=cod_regione,
                territorio=territorio,
                ruolo=ruolo,
                tema=tema,
                natura=natura,
                limit=limit,
                offset=offset,
            )
        return _with_sources(out, out.get("source_url"))

    @mcp.tool(annotations=_READ_ONLY)
    async def opencoesione_funding_capacity(
        cod_comune: str | None = None,
        tema: str | None = None,
        ciclo: str | None = None,
        territorio: str | None = None,
    ) -> dict[str, Any]:
        """Historical delivery capacity of a territory: spend ratio + completed projects.

        Workflow tool for feasibility assessments: `spend_ratio` is total
        payments / total public cost (how much of the secured funding was
        actually spent), `conclusi_ratio` is completed/total projects. A low
        spend ratio is an honest signal that new funding proposals need
        delivery-capacity caveats. Computed from the official territorial
        aggregates in a single call.

        Args:
            cod_comune: ISTAT comune code (e.g. "072006" for Bari).
            tema: Optional theme slug to scope the ratio to one policy theme
                (per-state breakdown not available per theme).
            ciclo: Optional programming cycle (e.g. "2014-2020").
            territorio: Explicit territory slug (alternative to cod_comune,
                also accepts provinces/regions, e.g. "puglia-regione").
        """
        async with OpenCoesioneClient() as c:
            cap = await c.funding_capacity(
                cod_comune=cod_comune, tema=tema, ciclo=ciclo, territorio=territorio
            )
        out = cap.model_dump()
        return _with_sources(out, cap.source_url)

    @mcp.tool(annotations=_READ_ONLY)
    async def opencoesione_resolve_territorio(
        nome: str | None = None,
        cod_comune: str | None = None,
        cod_provincia: str | None = None,
        cod_regione: str | None = None,
        tipo: str | None = None,
    ) -> dict[str, Any]:
        """Resolve a place name or ISTAT code to the OpenCoesione territory record.

        Returns the territory slug (used by every other filter), its type and
        ISTAT codes. Call this FIRST when the query names a place and you do
        not have its ISTAT code.

        Args:
            nome: Place name as written by the user (e.g. "Barletta", "Puglia").
            cod_comune: ISTAT comune code, alternative to nome.
            cod_provincia: ISTAT province code, alternative to nome.
            cod_regione: ISTAT region code, alternative to nome.
            tipo: Restrict name matches to C (comune) | P (provincia) | R (regione).
        """
        async with OpenCoesioneClient() as c:
            t = await c.resolve_territorio(
                cod_comune=cod_comune,
                cod_provincia=cod_provincia,
                cod_regione=cod_regione,
                nome=nome,
                tipo=tipo,
            )
            params: dict[str, Any] = {}
            if nome:
                params["denominazione"] = nome
            if tipo:
                params["tipo"] = tipo
            src = c.source_url("territori.json", params or None)
        if t is None:
            return _with_sources(
                {
                    "found": False,
                    "hint": (
                        "Nessun territorio corrispondente. Verifica il nome o il codice "
                        "ISTAT (es. comune '072006')."
                    ),
                    "source_url": src,
                },
                src,
            )
        out = t.model_dump()
        out["found"] = True
        out["source_url"] = src
        return _with_sources(out, src)

    @mcp.tool(annotations=_READ_ONLY)
    async def opencoesione_reference_values() -> dict[str, Any]:
        """Valid filter values discovered on the live API (themes, natures, states, cycles).

        Use this when a filtered call errors on an invalid slug — the API
        silently ignores unknown parameters, so this server validates them
        client-side against these enumerations.
        """
        return {
            "temi": list(TEMI),
            "nature": list(NATURE),
            "stati": list(STATI),
            "cicli": list(CICLI),
            "licenza": LICENZA_API,
        }

    # ── local aggregates — registered ONLY when OPENCOESIONE_DB_URL is set ──
    if local_db.db_url():
        register_local_tools(mcp)


def register_local_tools(mcp: FastMCP) -> None:
    """Register `opencoesione_query_local` (requires the populated local mirror)."""

    @mcp.tool(annotations=_READ_ONLY)
    async def opencoesione_query_local(
        kind: Literal[
            "spend_by_tema", "capacity", "top_soggetti", "compare_comuni",
            "similar_projects", "gap_by_tema", "stalled_projects",
        ],
        cod_comune: str | None = None,
        cod_comuni: list[str] | None = None,
        cod_provincia: str | None = None,
        cod_regione: str | None = None,
        tema: str | None = None,
        ciclo: str | None = None,
        limit: int = 10,
        min_peers: int = 3,
        soglia_ratio: float = 0.2,
    ) -> dict[str, Any]:
        """Heavy aggregate queries on the LOCAL OpenCoesione mirror (full bulk dataset).

        Prefer this over the live-API tools for aggregate questions: it scans
        the entire dataset, which the paginated API cannot. Use the live tools
        for puntual detail (single project, fresh search).

        Kinds:
          - spend_by_tema: funding/payments per theme for one comune.
          - capacity: spend ratio + completed/total projects for one comune.
          - top_soggetti: most recurrent implementing bodies in a territory
            (one of cod_comune / cod_provincia / cod_regione).
          - compare_comuni: side-by-side totals for several comuni (cod_comuni).
          - similar_projects: projects funded by COMPARABLE comuni (same
            region, population 0.5×–2×) — the "done elsewhere" idea generator.
            Requires cod_comune + the comuni registry (`make comuni-sync`).
          - gap_by_tema: themes where ≥min_peers comparable comuni funded
            projects and this comune has ZERO — the "gap" idea generator.
          - stalled_projects: local non-completed projects with spend ratio
            below soglia_ratio — the "unfinished" idea generator.

        Args:
            kind: One of the seven query kinds above (no free-form SQL).
            cod_comune: ISTAT comune code, e.g. "072006".
            cod_comuni: List of ISTAT comune codes (compare_comuni).
            cod_provincia: ISTAT province code, e.g. "072" (top_soggetti).
            cod_regione: ISTAT region code without leading zeros, e.g. "16".
            tema: Theme filter — accepts API slugs ('trasporti') or label
                fragments, case-insensitive.
            ciclo: Programming cycle, e.g. "2014-2020".
            limit: Max rows for top_soggetti / similar_projects (1-50).
            min_peers: gap_by_tema — min comparable comuni active on a theme.
            soglia_ratio: stalled_projects — spend-ratio threshold (default 0.2).
        """
        if kind == "spend_by_tema":
            if not cod_comune:
                raise ValueError("spend_by_tema richiede cod_comune")
            rows: Any = await local_db.spend_by_tema(cod_comune, ciclo)
        elif kind == "capacity":
            if not cod_comune:
                raise ValueError("capacity richiede cod_comune")
            rows = await local_db.capacity(cod_comune, ciclo)
        elif kind == "top_soggetti":
            rows = await local_db.top_soggetti(
                cod_comune=cod_comune,
                cod_provincia=cod_provincia,
                cod_regione=cod_regione,
                limit=limit,
            )
        elif kind == "compare_comuni":
            if not cod_comuni:
                raise ValueError("compare_comuni richiede cod_comuni (lista di codici ISTAT)")
            rows = await local_db.compare_comuni(cod_comuni, tema=tema, ciclo=ciclo)
        elif kind == "similar_projects":
            if not cod_comune:
                raise ValueError("similar_projects richiede cod_comune")
            rows = await local_db.similar_projects(cod_comune, tema=tema, ciclo=ciclo,
                                                   limit=limit)
        elif kind == "gap_by_tema":
            if not cod_comune:
                raise ValueError("gap_by_tema richiede cod_comune")
            rows = await local_db.gap_by_tema(cod_comune, ciclo=ciclo, min_peers=min_peers)
        elif kind == "stalled_projects":
            if not cod_comune:
                raise ValueError("stalled_projects richiede cod_comune")
            rows = await local_db.stalled_projects(cod_comune, soglia_ratio=soglia_ratio,
                                                   ciclo=ciclo)
        else:  # pragma: no cover — Literal already guards this
            raise ValueError(f"kind {kind!r} non supportato")

        info = await local_db.dataset_info()
        # NB: don't call this key "result" — FastMCP wraps non-dict returns
        # under a top-level "result" and clients unwrap it; a same-named key
        # here would be swallowed by that unwrapping.
        out: dict[str, Any] = {
            "kind": kind,
            "rows": rows,
            "dataset": info,
            "source_url": _BULK_DATASET_URL,
            "licenza": LICENZA_BULK,
        }
        out["sources"] = [
            {
                "url": _BULK_DATASET_URL,
                "estratto_il": str(info.get("ingested_at") or date.today().isoformat()),
                "licenza": LICENZA_BULK,
            }
        ]
        return out
