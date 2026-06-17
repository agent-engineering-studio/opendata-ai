"""Tool MCP per la maturità open-data. Delegano al motore puro di opendata_core
(harvest via CKAN + scoring deterministico) e usano Haiku solo per il semantico."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from opendata_core.maturity import (
    DatasetInput,
    DimensionScores,
    MaturityResult,
    QualityScore,
    assess_entity,
    assess_quality,
)
from opendata_core.maturity.harvest import HarvestResult, harvest_entity

from .semantic import semantic_clarity_map


def _quality_dict(q: QualityScore) -> dict[str, Any]:
    return {
        "dataset_id": q.dataset_id,
        "stars_5": q.stars_5,
        "fair": {"F": q.fair_f, "A": q.fair_a, "I": q.fair_i, "R": q.fair_r, "mean": round(q.fair_mean, 3)},
        "dcat_ap_it": q.dcat_ap_it,
        "iso25012": q.iso25012,
        "iso25012_detail": q.iso25012_detail,
        "license_open": q.license_open,
        "hvd_category": q.hvd_category,
        "freshness_days": q.freshness_days,
    }


def _scores_dict(s: DimensionScores) -> dict[str, Any]:
    return s.as_dict()


def _result_dict(h: HarvestResult, res: MaturityResult) -> dict[str, Any]:
    return {
        "entity": h.entity,
        "ckan_org_id": h.ckan_org_id,
        "org_title": h.org_title,
        "n_datasets": res.n_datasets,
        "total_on_portal": h.total,
        "truncated": h.truncated,
        "scores": _scores_dict(res.scores),
        "recommendations": [
            {"code": r.code, "severity": r.severity, "dimension": r.dimension,
             "message": r.message, "affected_count": r.affected_count}
            for r in res.recommendations
        ],
    }


async def _semantic_for(datasets: tuple[DatasetInput, ...], use_semantic: bool) -> dict[str, float]:
    if not use_semantic:
        return {}
    items = [
        {"id": d.id, "title": d.title or "", "description": d.description or ""} for d in datasets
    ]
    return await semantic_clarity_map(items)


async def _assess(entity: str, base_url: str | None, max_datasets: int, use_semantic: bool):
    harvest = await harvest_entity(entity, base_url=base_url, max_datasets=max_datasets)
    semantic = await _semantic_for(harvest.datasets, use_semantic)
    result = assess_entity(list(harvest.datasets), semantic=semantic)
    return harvest, result


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def maturity_harvest_entity(
        entity: str, base_url: str | None = None, max_datasets: int = 50
    ) -> dict[str, Any]:
        """Raccoglie i dataset di un ente da CKAN (organization_show + package_search).

        `entity`: nome/slug/id dell'organizzazione CKAN. Ritorna l'organizzazione e
        un riepilogo normalizzato dei dataset (eventualmente troncato a max_datasets).
        """
        h = await harvest_entity(entity, base_url=base_url, max_datasets=max_datasets)
        return {
            "entity": h.entity,
            "ckan_org_id": h.ckan_org_id,
            "ckan_org_name": h.ckan_org_name,
            "org_title": h.org_title,
            "total_on_portal": h.total,
            "truncated": h.truncated,
            "datasets": [
                {
                    "id": d.id, "title": d.title, "theme": d.theme,
                    "formats": list(d.formats), "license_open": d.license_is_open,
                    "modified": d.modified.isoformat() if d.modified else None,
                }
                for d in h.datasets
            ],
        }

    @mcp.tool()
    async def maturity_assess_quality(dataset: dict[str, Any]) -> dict[str, Any]:
        """Valuta la qualità di un singolo dataset CKAN (5-star/FAIR/DCAT-AP_IT/ISO25012/HVD).

        `dataset`: pacchetto CKAN (Action API). Il giudizio semantico (Haiku) NON è
        applicato qui; usa maturity_score_overall per l'analisi completa dell'ente.
        """
        ds = DatasetInput.from_ckan(dataset)
        return _quality_dict(assess_quality(ds))

    @mcp.tool()
    async def maturity_score_overall(
        entity: str, base_url: str | None = None, max_datasets: int = 50, use_semantic: bool = True
    ) -> dict[str, Any]:
        """Assessment completo di un ente: harvest → qualità → 4 dimensioni → livello ODM
        → raccomandazioni. Usa Haiku per la comprensibilità delle descrizioni se disponibile."""
        h, res = await _assess(entity, base_url, max_datasets, use_semantic)
        return _result_dict(h, res)

    @mcp.tool()
    async def maturity_score_dimension(
        entity: str, dimension: str, base_url: str | None = None, max_datasets: int = 50
    ) -> dict[str, Any]:
        """Punteggio (0–100) di una singola dimensione: policy | portal | quality | impact."""
        dim = dimension.strip().lower()
        if dim not in {"policy", "portal", "quality", "impact"}:
            raise ValueError("dimension deve essere uno di: policy, portal, quality, impact")
        _, res = await _assess(entity, base_url, max_datasets, use_semantic=False)
        return {"entity": entity, "dimension": dim, "score": getattr(res.scores, dim)}

    @mcp.tool()
    async def maturity_compare_entities(
        entities: list[str], base_url: str | None = None, max_datasets: int = 50
    ) -> dict[str, Any]:
        """Benchmark tra enti: ritorna overall/livello/dimensioni per ciascuno, ordinati."""
        rows: list[dict[str, Any]] = []
        for ent in entities:
            try:
                _, res = await _assess(ent, base_url, max_datasets, use_semantic=False)
            except Exception as exc:  # noqa: BLE001 — un ente non risolvibile non blocca il benchmark
                rows.append({"entity": ent, "error": str(exc)})
                continue
            rows.append({"entity": ent, "n_datasets": res.n_datasets, **_scores_dict(res.scores)})
        ranked = sorted(
            (r for r in rows if "overall" in r), key=lambda r: r["overall"], reverse=True
        )
        errors = [r for r in rows if "error" in r]
        return {"ranking": ranked, "errors": errors}
