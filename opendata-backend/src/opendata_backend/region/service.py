"""Servizio del cruscotto regionale (#229).

Costruisce le `ComuneSummary` dal warehouse — tutti i comuni della regione
(`ComuneAnagrafica`) arricchiti con l'ultimo assessment di maturità (per nome
Entity, come /dataplan) e la copertura HVD (`DatasetQuality.hvd_category`) — e le
dà in pasto al motore puro `opendata_core.region.aggregate_region`. Fail-safe: se
il DB non ha ancora dati la vista esce comunque (comuni non valutati = zero dati).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opendata_core.dataplan.state import accompaniment_state
from opendata_core.region import ComuneSummary, aggregate_region

from ..config import Settings, region_name
from ..db.models import ComuneAnagrafica
from ..db.territory_models import DatasetQuality, Entity, MaturityAssessment

_DIM_COLUMNS = (
    ("policy", "score_policy"),
    ("portal", "score_portal"),
    ("quality", "score_quality"),
    ("impact", "score_impact"),
)


def _f(v: Any) -> float | None:
    return float(v) if v is not None else None


async def _load_summaries(
    session: AsyncSession, settings: Settings
) -> tuple[list[ComuneSummary], dict[str, str | None]]:
    """Le sintesi-comune della regione + mappa istat→provincia (per /comuni)."""
    cod_regione = settings.region_istat or None
    stmt = select(ComuneAnagrafica)
    if cod_regione:
        stmt = stmt.where(ComuneAnagrafica.cod_regione == cod_regione)
    comuni = list((await session.execute(stmt.order_by(ComuneAnagrafica.nome))).scalars().all())
    if not comuni:
        return [], {}

    names = {c.nome for c in comuni}
    # Entity per nome (stesso aggancio fragile ma coerente con /dataplan).
    ent_rows = (
        await session.execute(select(Entity.id, Entity.name).where(Entity.name.in_(names)))
    ).all()
    name_to_entity = {name: eid for eid, name in ent_rows}
    entity_ids = list(name_to_entity.values())

    # Ultimo assessment per entity (senza window function → riduzione in Python).
    latest: dict[int, MaturityAssessment] = {}
    if entity_ids:
        rows = (
            await session.execute(
                select(MaturityAssessment)
                .where(MaturityAssessment.entity_id.in_(entity_ids))
                .order_by(
                    MaturityAssessment.entity_id,
                    MaturityAssessment.assessed_at.desc(),
                    MaturityAssessment.id.desc(),
                )
            )
        ).scalars().all()
        for a in rows:
            latest.setdefault(a.entity_id, a)

    # Categorie HVD coperte per entity (dai dataset valutati).
    hvd: dict[int, set[str]] = {}
    if entity_ids:
        hvd_rows = (
            await session.execute(
                select(DatasetQuality.entity_id, DatasetQuality.hvd_category)
                .where(
                    DatasetQuality.entity_id.in_(entity_ids),
                    DatasetQuality.hvd_category.is_not(None),
                )
                .distinct()
            )
        ).all()
        for eid, cat in hvd_rows:
            if eid is not None and cat:
                hvd.setdefault(eid, set()).add(cat)

    summaries: list[ComuneSummary] = []
    provincia_by_istat: dict[str, str | None] = {}
    for c in comuni:
        provincia_by_istat[c.cod_comune] = c.cod_provincia
        eid = name_to_entity.get(c.nome)
        a = latest.get(eid) if eid is not None else None
        if a is not None:
            dims = {key: _f(getattr(a, col)) for key, col in _DIM_COLUMNS}
            dimensioni = {k: v for k, v in dims.items() if v is not None}
            n_dataset = int((a.details_jsonb or {}).get("n_datasets") or 0)
            overall = _f(a.score_overall)
            hvd_cats = sorted(hvd.get(eid, set())) if eid is not None else []
        else:
            dimensioni, n_dataset, overall, hvd_cats = {}, 0, None, []
        summaries.append(
            ComuneSummary(
                istat=c.cod_comune,
                nome=c.nome,
                popolazione=c.popolazione,
                overall=overall,
                dimensioni=dimensioni,
                n_dataset=n_dataset,
                hvd_categorie=hvd_cats,
            )
        )
    return summaries, provincia_by_istat


async def overview(session: AsyncSession, settings: Settings) -> dict[str, Any]:
    """Vista d'insieme regionale (KPI + distribuzione + dove intervenire)."""
    summaries, _ = await _load_summaries(session, settings)
    ov = aggregate_region(
        summaries,
        regione=region_name(settings) or "",
        cod_regione=settings.region_istat or "",
        comuni_totali=len(summaries),
    )
    return ov.model_dump()


async def comuni(
    session: AsyncSession, settings: Settings, *, provincia: str | None = None
) -> dict[str, Any]:
    """Classifica dei comuni della regione (nome, stato, overall), filtrabile
    per provincia. Ordinati per maturità decrescente (non valutati in fondo)."""
    summaries, prov = await _load_summaries(session, settings)
    rows: list[dict[str, Any]] = []
    for s in summaries:
        p = prov.get(s.istat)
        if provincia and p != provincia:
            continue
        stato = accompaniment_state(n_dataset=s.n_dataset, overall=s.overall).stato
        rows.append({
            "istat": s.istat,
            "nome": s.nome,
            "provincia": p,
            "popolazione": s.popolazione,
            "overall": s.overall,
            "stato": stato,
            "n_dataset": s.n_dataset,
        })
    # Overall desc, non valutati (None) in fondo, poi per nome.
    rows.sort(key=lambda r: (0 if r["overall"] is not None else 1, -(r["overall"] or 0), r["nome"]))
    return {
        "regione": region_name(settings) or "",
        "cod_regione": settings.region_istat or "",
        "provincia": provincia,
        "totale": len(rows),
        "comuni": rows,
    }
