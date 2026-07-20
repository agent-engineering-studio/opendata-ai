"""OpenPNRR tool implementations registered on the FastMCP server.

All tools are thin wrappers over ``opendata_core.openpnrr.OpenPnrrClient`` and
return structured dicts (like the other MCP servers in this repo). Every result
carries:
  - ``source_url`` — the resolvable API URL of that exact response (the
    deterministic citation hook for the orchestrator's resource capture);
  - ``sources`` — a block with URL + extraction date + licence (ODbL 1.0).

Territorial scoping accepts an ISTAT code (``istat_id``) which the client
resolves to an OpenPNRR territory id via /territori, or an explicit numeric
``territori`` id.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from opendata_core.openpnrr import LICENZA, OpenPnrrClient

_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)

#: Cap the serialized size of list payloads to stay within LLM context budgets.
_MAX_RESULTS = 50


def _scalar(v: Any) -> Any:
    """I modelli piccoli passano liste dove serve uno scalare — prendi il primo."""
    if isinstance(v, list):
        return v[0] if v else None
    return v


def _with_sources(payload: dict[str, Any], *urls: str | None) -> dict[str, Any]:
    """Attach the standard `sources` block (URL + extraction date + licence)."""
    seen: list[str] = []
    for u in urls:
        if u and u not in seen:
            seen.append(u)
    payload["sources"] = [
        {"url": u, "estratto_il": date.today().isoformat(), "licenza": LICENZA}
        for u in seen
    ]
    return payload


def register_tools(mcp: FastMCP) -> None:
    """Register all OpenPNRR tools on the given FastMCP instance."""

    @mcp.tool(annotations=_READ_ONLY)
    async def openpnrr_resolve_territorio(
        nome: str | None = None,
        istat_id: str | None = None,
        opdm_id: str | None = None,
        tipologia: str | None = None,
    ) -> dict[str, Any]:
        """Resolve a place name or ISTAT code to the OpenPNRR territory record.

        Returns the territory `id` (used by every other territorial filter), its
        slug, ISTAT code and type. Call this FIRST when the query names a place
        and you do not already have its OpenPNRR id.

        Args:
            nome: Place name as written by the user (e.g. "Gioia del Colle").
            istat_id: ISTAT code (e.g. "072021" for a comune) — maps 1:1 onto the
                codes used elsewhere in the platform.
            opdm_id: openpolis OPDM id, alternative to the above.
            tipologia: Restrict name matches to C (comune) | P (provincia) |
                R (regione) | E (ente).
        """
        async with OpenPnrrClient() as c:
            t = await c.resolve_territorio(
                istat_id=istat_id, opdm_id=opdm_id, nome=nome, tipologia=tipologia
            )
            params: dict[str, Any] = {}
            if istat_id:
                params["istat_id"] = istat_id
            elif nome:
                params["denominazione"] = nome
            src = c.source_url("territori", params or None)
        if t is None:
            return _with_sources(
                {"found": False,
                 "hint": "Nessun territorio corrispondente. Verifica nome o codice ISTAT.",
                 "source_url": src, "licenza": LICENZA},
                src,
            )
        out = t.model_dump()
        out["found"] = True
        out["source_url"] = src
        out["licenza"] = LICENZA
        return _with_sources(out, src)

    @mcp.tool(annotations=_READ_ONLY)
    async def openpnrr_search_progetti(
        istat_id: str | None = None,
        territori: int | str | None = None,
        descrizione: str | None = None,
        misura_codice_identificativo: str | None = None,
        componente_codice_identificativo: str | None = None,
        missione_codice_identificativo: str | None = None,
        organizzazioni: str | int | None = None,
        tema: str | int | None = None,
        validato: bool | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search PNRR-funded projects, filterable by territory, measure, mission, theme.

        Returns slim project records (id, CLP, title, CUP, measure, implementer,
        state, PNRR/total funding) plus `total`, `has_more`, `next_offset` for
        pagination. The dataset is huge (~280k) — a filter is effectively required.

        Args:
            istat_id: ISTAT code of the territory (e.g. "072021"); resolved internally.
            territori: Explicit OpenPNRR territory id (alternative to istat_id).
            descrizione: Free-text match on the project description/title.
            misura_codice_identificativo: Measure code (e.g. "M1C1I1.1").
            componente_codice_identificativo: Component code (e.g. "M1C1").
            missione_codice_identificativo: Mission code (e.g. "M1").
            organizzazioni: Organisation (implementing body) id.
            tema: Theme id/slug.
            validato: Keep only validated projects when true.
            limit: Max results per page (default 20, hard-capped at 50).
            offset: Pagination offset — must be a multiple of `limit`.
        """
        limit = max(1, min(int(limit), _MAX_RESULTS))
        async with OpenPnrrClient() as c:
            out = await c.search_progetti(
                istat_id=istat_id,
                territori=_scalar(territori),
                descrizione=descrizione,
                misura_codice_identificativo=misura_codice_identificativo,
                componente_codice_identificativo=componente_codice_identificativo,
                missione_codice_identificativo=missione_codice_identificativo,
                organizzazioni=_scalar(organizzazioni),
                tema=_scalar(tema),
                validato=validato,
                limit=limit,
                offset=offset,
            )
        return _with_sources(out, out.get("source_url"))

    @mcp.tool(annotations=_READ_ONLY)
    async def openpnrr_get_progetto(progetto_id: int | str) -> dict[str, Any]:
        """Full detail of one PNRR project by its numeric id.

        Includes the complete financing breakdown (PNRR / PNC / stato / regione /
        comune / UE / privato…), the payments list with `pagamenti_totale`
        (sum of actual payments), CUP classification, timeline and iter phase.

        Args:
            progetto_id: Numeric project id as returned by openpnrr_search_progetti
                (the `id` field, e.g. 184335).
        """
        async with OpenPnrrClient() as c:
            out = await c.get_progetto(progetto_id)
        return _with_sources(out, out.get("source_url"))

    @mcp.tool(annotations=_READ_ONLY)
    async def openpnrr_search_misure(
        codice_misura: str | None = None,
        componente_codice: str | None = None,
        tipologia: str | None = None,
        tipo_riforma: str | None = None,
        tipo_investimento: str | None = None,
        status: str | None = None,
        istat_id: str | None = None,
        territori: int | str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search PNRR measures (investments and reforms) by code, component, type, status.

        Args:
            codice_misura: Measure code (e.g. "M1C1I1.1").
            componente_codice: Component code (e.g. "M1C1").
            tipologia: Measure type filter.
            tipo_riforma: Reform-type filter.
            tipo_investimento: Investment-type filter.
            status: Measure status filter.
            istat_id: ISTAT code to scope measures touching a territory.
            territori: Explicit OpenPNRR territory id (alternative to istat_id).
            limit: Max results per page (default 20, hard-capped at 50).
            offset: Pagination offset — must be a multiple of `limit`.
        """
        limit = max(1, min(int(limit), _MAX_RESULTS))
        async with OpenPnrrClient() as c:
            out = await c.search_misure(
                codice_misura=codice_misura,
                componente_codice=componente_codice,
                tipologia=tipologia,
                tipo_riforma=tipo_riforma,
                tipo_investimento=tipo_investimento,
                status=status,
                istat_id=istat_id,
                territori=_scalar(territori),
                limit=limit,
                offset=offset,
            )
        return _with_sources(out, out.get("source_url"))

    @mcp.tool(annotations=_READ_ONLY)
    async def openpnrr_search_scadenze(
        misure_codice_identificativo: str | None = None,
        status: str | None = None,
        tempistica_completamento_anno: int | None = None,
        tempistica_completamento_trimestre: str | None = None,
        ita_ue: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search PNRR deadlines/milestones (target & milestone, ITA/UE) by measure and time.

        Args:
            misure_codice_identificativo: Measure code the deadline belongs to.
            status: Deadline status filter.
            tempistica_completamento_anno: Target completion year (e.g. 2026).
            tempistica_completamento_trimestre: Target completion quarter (e.g. "T4").
            ita_ue: Scope of the milestone: "ITA" (national) or "UE" (European).
            limit: Max results per page (default 20, hard-capped at 50).
            offset: Pagination offset — must be a multiple of `limit`.
        """
        limit = max(1, min(int(limit), _MAX_RESULTS))
        async with OpenPnrrClient() as c:
            out = await c.search_scadenze(
                misure_codice_identificativo=misure_codice_identificativo,
                status=status,
                tempistica_completamento_anno=tempistica_completamento_anno,
                tempistica_completamento_trimestre=tempistica_completamento_trimestre,
                ita_ue=ita_ue,
                limit=limit,
                offset=offset,
            )
        return _with_sources(out, out.get("source_url"))

    @mcp.tool(annotations=_READ_ONLY)
    async def openpnrr_reference_struttura() -> dict[str, Any]:
        """PNRR structure reference: missions, components, themes, priorities.

        Small static reference (6-7 missions → 17 components → measures) useful to
        resolve the codes used as filters in openpnrr_search_progetti /
        openpnrr_search_misure. Each mission/component carries its PNRR/FSC/
        complementary amounts.
        """
        async with OpenPnrrClient() as c:
            out = await c.reference_struttura()
        return _with_sources(out, *(out.get("sources") or []))
