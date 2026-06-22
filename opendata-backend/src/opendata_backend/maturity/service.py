"""Orchestrazione dell'assessment di maturità di un ente.

harvest (cap) → assess (deterministico + Haiku semantico opzionale) → persisti
snapshot storicizzati → costruisci scorecard (4 dim, livello, raccomandazioni,
trend, mediana cluster). Cache Redis per (entity, base_url).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from statistics import median
from typing import Any, Callable

from opendata_core.maturity import (
    MaturityResult,
    analyze_gaps,
    assess_entity,
    build_guida_opendata,
    infer_entity_type,
)
from opendata_core.maturity.harvest import HarvestResult, harvest_entity
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache.store import cache_get, cache_set
from ..config import Settings
from ..config_files import maturity_coverage, maturity_weights, portali_regionali
from ..db.repositories import maturity as repo
from ..llm import llm_configured
from .semantic import semantic_clarity_map

log = logging.getLogger("opendata-backend.maturity")


def _weights() -> dict[str, float]:
    return maturity_weights()["weights"]


def _coverage_templates() -> dict[str, dict[str, int]] | None:
    """Template di copertura per tipo di ente (config); None → default del motore."""
    try:
        return maturity_coverage().get("templates")
    except Exception:  # config assente/malformata: il motore usa i suoi default
        log.warning("maturity: config copertura non caricabile, uso i default", exc_info=True)
        return None


def _regional_ckan(istat_code: str | None) -> str | None:
    """Portale CKAN regionale per la provincia del comune (prime 3 cifre ISTAT)."""
    if not istat_code:
        return None
    prov = str(istat_code).strip().zfill(6)[:3]
    return (portali_regionali().get("province_ckan") or {}).get(prov)


async def _resolve_harvest(
    *, entity: str, comune_nome: str | None, istat_code: str | None,
    base_url: str | None, max_datasets: int,
) -> tuple[HarvestResult, str | None]:
    """Risolve il portale del comune provando più candidati, fermandosi al primo
    con dataset. Best-effort/fail-safe: ogni tentativo è isolato. Ritorna
    (HarvestResult, base_url risolto). Se nessuno trova dati, ritorna il primo
    (vuoto) → l'assessment procede a "Dato insufficiente" + guida.
    """
    import re

    def _slug(s: str) -> str:
        # "Regione Puglia" → "regione-puglia"; "Comune di Bari" → "comune-di-bari".
        return re.sub(r"[^a-z0-9]+", "-", s.strip().lower()).strip("-")

    # Candidati in ordine: (base_url, query). None = dati.gov.it (default CkanClient).
    # Includiamo anche la forma SLUG del nome (org CKAN usa lo slug, non il nome con
    # spazi) così l'utente può digitare il nome esteso (es. "Regione Puglia").
    base_name = (comune_nome or entity or "").strip()
    forms = [entity, comune_nome or "", _slug(entity), _slug(comune_nome or "")]
    # Le org CKAN portano spesso un prefisso istituzionale ("Comune di X",
    # "Regione X") mentre l'utente digita il nome nudo ("Bari", "Emilia Romagna").
    # Aggiungiamo le forme prefissate così entrambe risolvono l'organizzazione.
    if base_name:
        if istat_code:  # è un comune
            forms += [f"comune di {base_name}", f"comune-di-{_slug(base_name)}"]
        else:  # ente non comunale: spesso una Regione
            forms += [f"regione {base_name}", f"regione-{_slug(base_name)}"]
    queries: list[str] = []
    for q in forms:
        q = q.strip()
        if q and q not in queries:
            queries.append(q)
    candidates: list[tuple[str | None, str]] = [(base_url, q) for q in queries]
    reg = _regional_ckan(istat_code)
    if reg:
        candidates += [(reg, comune_nome.strip() if comune_nome else entity), (reg, _slug(comune_nome or entity))]

    first: HarvestResult | None = None
    first_base: str | None = base_url
    seen: set[tuple[str | None, str]] = set()
    for cand_base, query in candidates:
        if (cand_base, query.lower()) in seen:
            continue
        seen.add((cand_base, query.lower()))
        try:
            res = await harvest_entity(query, base_url=cand_base, max_datasets=max_datasets)
        except Exception:
            log.warning("maturity: harvest fallito per %s su %s", query, cand_base or "dati.gov.it",
                        exc_info=True)
            continue
        if first is None:
            first, first_base = res, cand_base
        if res.datasets:
            return res, cand_base
    # nessun candidato con dataset
    if first is None:
        first = HarvestResult(entity=entity, ckan_org_id=None, ckan_org_name=None,
                              org_title=None, total=0, datasets=())
    return first, first_base


def _cache_key(entity: str, base_url: str | None) -> str:
    return f"od:maturity:{base_url or 'default'}:{entity.strip().lower()}"


def _details(result: MaturityResult, harvest: HarvestResult) -> dict[str, Any]:
    return {
        "n_datasets": result.n_datasets,
        "total_on_portal": harvest.total,
        "truncated": harvest.truncated,
        "insufficient_data": result.insufficient_data,
        "dimensions": result.scores.as_dict(),
        "recommendations": [
            {"code": r.code, "severity": r.severity, "dimension": r.dimension,
             "message": r.message, "affected_count": r.affected_count}
            for r in result.recommendations
        ],
        "dimension_breakdown": [b.as_dict() for b in result.breakdown],
        "coverage": result.coverage.as_dict() if result.coverage is not None else None,
        # Gap analysis (#50): direzione verso il prossimo livello ODM — collo di
        # bottiglia + roadmap quick-win/strategici. Vuota se dati insufficienti.
        "gap": (
            None if result.insufficient_data
            else analyze_gaps(
                result.scores, result.recommendations, weights=_weights()
            ).as_dict()
        ),
    }


async def _semantic(harvest: HarvestResult, settings: Settings) -> dict[str, float]:
    if not llm_configured(settings):
        return {}
    items = [
        {"id": d.id, "title": d.title or "", "description": d.description or ""}
        for d in harvest.datasets
    ]
    return await semantic_clarity_map(items, settings=settings)


async def run_assessment(
    session: AsyncSession, *, entity: str, base_url: str | None, settings: Settings,
    force: bool = False, istat_code: str | None = None, comune_nome: str | None = None,
    emit: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Esegue (o riusa da cache) l'assessment di un ente e ritorna la scorecard.

    `istat_code` (opzionale) collega l'ente a un comune: la domanda di riuso non
    soddisfatta (gap di dato) riduce l'Impact — anello valore⇄maturità. La
    risoluzione del portale prova dati.gov.it e (se vuoto) il portale regionale.

    `emit` (opzionale) riceve eventi di avanzamento granulari per lo streaming:
    `{"event":"status","phase":"<fase>","state":"start|end", ...}`. Senza, è
    un no-op (chiamata classica sincrona). Le fasi indipendenti (analisi
    semantica Haiku + domanda di riuso) girano in PARALLELO.
    """
    _emit = emit or (lambda _e: None)
    key = _cache_key(entity, base_url)
    if not force:
        cached = await cache_get(key)
        if cached is not None:
            _emit({"event": "status", "phase": "cache", "state": "hit"})
            return cached

    # 1) Raccolta dataset dal portale (la fase più lunga: prova dati.gov.it e,
    #    se vuoto, il portale regionale).
    _emit({"event": "status", "phase": "portale", "state": "start"})
    harvest, base_url = await _resolve_harvest(
        entity=entity, comune_nome=comune_nome, istat_code=istat_code,
        base_url=base_url, max_datasets=settings.maturity_max_datasets,
    )
    if harvest.truncated:
        log.info(
            "maturity: ente %s troncato a %d/%d dataset",
            entity, len(harvest.datasets), harvest.total,
        )
    _emit({
        "event": "status", "phase": "portale", "state": "end",
        "n_datasets": len(harvest.datasets), "total": harvest.total,
        "portal": base_url,
    })

    # 2) Analisi semantica (Haiku) + domanda di riuso (DB) — INDIPENDENTI, in
    #    parallelo: il costo passa da somma a max. La semantica non tocca il DB,
    #    la domanda di riuso non tocca l'LLM → nessun uso concorrente di session.
    _emit({"event": "status", "phase": "analisi", "state": "start"})

    async def _demand() -> dict[str, Any]:
        if not istat_code:
            return {"count": 0, "items": [], "penalty": 0.0}
        from .reuse_demand import unmet_reuse_demand

        return await unmet_reuse_demand(session, istat_code=istat_code)

    semantic, demand = await asyncio.gather(_semantic(harvest, settings), _demand())
    _emit({"event": "status", "phase": "analisi", "state": "end"})

    # 3) Punteggio deterministico (4 dimensioni ODM + copertura tematica) — veloce.
    #    Il tipo di ente (comune/regione/provincia/ente) seleziona la collection
    #    ottimale attesa: lo deduciamo da nome + presenza del codice ISTAT.
    _emit({"event": "status", "phase": "punteggio", "state": "start"})
    entity_type = infer_entity_type(
        harvest.org_title or comune_nome or entity, has_istat=bool(istat_code)
    )
    result = assess_entity(
        list(harvest.datasets), weights=_weights(), semantic=semantic,
        reuse_demand_penalty=demand["penalty"],
        entity_type=entity_type, coverage_templates=_coverage_templates(),
    )
    _emit({"event": "status", "phase": "punteggio", "state": "end"})

    # 4) Persistenza snapshot + scorecard.
    _emit({"event": "status", "phase": "salvataggio", "state": "start"})
    assessed_at = datetime.now(timezone.utc)
    ent = await repo.upsert_entity(
        session, name=harvest.org_title or entity, ckan_org_id=harvest.ckan_org_id,
        entity_type="ente", portal_url=base_url,
    )
    await repo.save_dataset_quality(
        session, entity_id=ent.id, qualities=result.dataset_quality, assessed_at=assessed_at
    )
    details = _details(result, harvest)
    details["unmet_reuse_demand"] = demand
    await repo.save_assessment(
        session, entity_id=ent.id, scores=result.scores,
        details=details, assessed_at=assessed_at,
    )
    await session.commit()

    scorecard = await build_scorecard(session, ent.id)
    if scorecard is not None:
        await cache_set(key, scorecard, ttl_seconds=settings.maturity_cache_ttl_seconds)
    _emit({"event": "status", "phase": "salvataggio", "state": "end"})
    return scorecard or {}


async def _cluster_median(session: AsyncSession, entity_type: str | None) -> float | None:
    rows = await repo.ranking(session, entity_type=entity_type)
    overalls = [float(a.score_overall or 0) for _, a in rows]
    return round(median(overalls), 1) if overalls else None


# Etichetta plurale del cluster di enti simili (per il testo "tra i N …").
_CLUSTER_PLURAL = {
    "comune": "comuni",
    "regione": "Regioni",
    "provincia": "Province",
    "ente": "enti",
}


async def _peer_comparison(session: AsyncSession, ent: Any) -> dict[str, Any] | None:
    """Confronto con enti simili: posizione + mediane (overall e per dimensione).

    Il cluster sono gli enti dello **stesso tipo** già valutati (stessa logica di
    `_cluster_median`, qui arricchita). Serve almeno un altro ente: con un solo
    elemento il confronto non ha senso e si restituisce ``None`` (la UI lo nasconde).
    """
    rows = await repo.ranking(session, entity_type=ent.type)  # ordinati desc per overall
    if len(rows) < 2:
        return None
    overalls = [float(a.score_overall or 0) for _, a in rows]
    median_dims = {
        "policy": round(median([float(a.score_policy or 0) for _, a in rows]), 1),
        "portal": round(median([float(a.score_portal or 0) for _, a in rows]), 1),
        "quality": round(median([float(a.score_quality or 0) for _, a in rows]), 1),
        "impact": round(median([float(a.score_impact or 0) for _, a in rows]), 1),
    }
    ids = [e.id for e, _ in rows]
    count = len(rows)
    rank = ids.index(ent.id) + 1 if ent.id in ids else None
    # "meglio del X% degli enti simili": quota di cluster sotto questo ente.
    better_than_pct = round((count - rank) / count * 100) if rank else None
    return {
        "cluster_label": _CLUSTER_PLURAL.get((ent.type or "").lower(), "enti"),
        "count": count,
        "rank": rank,
        "better_than_pct": better_than_pct,
        "median_overall": round(median(overalls), 1),
        "median_dimensions": median_dims,
    }


async def build_scorecard(session: AsyncSession, entity_id: int) -> dict[str, Any] | None:
    """Scorecard dell'ente dall'ultimo snapshot + trend + mediana cluster."""
    ent = await repo.get_entity(session, entity_id)
    if ent is None:
        return None
    latest = await repo.latest_assessment(session, entity_id)
    if latest is None:
        return None
    details = latest.details_jsonb or {}
    insufficient = bool(details.get("insufficient_data", False))
    # Comune senza/con pochi dati → guida operativa open-data (niente punteggi falsi).
    guida = (
        build_guida_opendata(
            ent.name,
            n_datasets=int(details.get("n_datasets") or 0),
            total_on_portal=int(details.get("total_on_portal") or 0),
        )
        if insufficient else None
    )
    trend = [
        {"assessed_at": a.assessed_at.isoformat(), "overall": float(a.score_overall or 0),
         "level": a.level}
        for a in await repo.assessment_trend(session, entity_id)
    ]
    return {
        "entity": {
            "id": ent.id, "name": ent.name, "type": ent.type, "region": ent.region,
            "ckan_org_id": ent.ckan_org_id,
        },
        "assessed_at": latest.assessed_at.isoformat(),
        "level": latest.level,
        "overall": float(latest.score_overall or 0),
        "dimensions": {
            "policy": float(latest.score_policy or 0),
            "portal": float(latest.score_portal or 0),
            "quality": float(latest.score_quality or 0),
            "impact": float(latest.score_impact or 0),
        },
        "recommendations": details.get("recommendations", []),
        "dimension_breakdown": details.get("dimension_breakdown", []),
        "coverage": details.get("coverage"),
        "gap": details.get("gap"),  # gap analysis (#50): direzione + roadmap
        "weights": _weights(),
        "n_datasets": details.get("n_datasets"),
        "truncated": details.get("truncated"),
        "insufficient_data": insufficient,
        "guida": guida,
        "unmet_reuse_demand": details.get("unmet_reuse_demand", {"count": 0, "items": [], "penalty": 0.0}),
        "trend": trend,
        "cluster_median": await _cluster_median(session, ent.type),
        # Confronto con enti simili (#50): posizione + mediane per dimensione.
        "peer_comparison": await _peer_comparison(session, ent),
    }


async def build_ranking(
    session: AsyncSession, *, entity_type: str | None, region: str | None
) -> dict[str, Any]:
    rows = await repo.ranking(session, entity_type=entity_type, region=region)
    items = [
        {
            "entity": {"id": e.id, "name": e.name, "type": e.type, "region": e.region},
            "overall": float(a.score_overall or 0), "level": a.level,
            "dimensions": {
                "policy": float(a.score_policy or 0), "portal": float(a.score_portal or 0),
                "quality": float(a.score_quality or 0), "impact": float(a.score_impact or 0),
            },
        }
        for e, a in rows
    ]
    overalls = [it["overall"] for it in items]
    return {
        "count": len(items),
        "median_overall": round(median(overalls), 1) if overalls else None,
        "ranking": items,
    }
