"""Aggregazione per ente: dimensioni 0–100, overall pesato, livello ODM, gap → raccomandazioni."""

from __future__ import annotations

from datetime import datetime

from .models import (
    DEFAULT_WEIGHTS,
    OPEN_FORMATS,
    DatasetInput,
    DimensionScores,
    MaturityResult,
    QualityScore,
    Recommendation,
    odm_level,
)
from .quality import assess_quality

_Pair = tuple[DatasetInput, QualityScore]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _has_open_format(ds: DatasetInput) -> bool:
    return bool({f.lower() for f in ds.formats} & OPEN_FORMATS)


def _severity(gap: float) -> str:
    if gap > 0.4:
        return "alta"
    if gap > 0.2:
        return "media"
    return "bassa"


def score_dimensions(
    pairs: list[_Pair], *, weights: dict[str, float] | None = None
) -> DimensionScores:
    """Calcola le 4 dimensioni (0–100), l'overall pesato e il livello ODM."""
    w = weights or DEFAULT_WEIGHTS
    if not pairs:
        return DimensionScores(0.0, 0.0, 0.0, 0.0, 0.0, odm_level(0.0))

    n = len(pairs)
    share_open_license = _mean([1.0 if q.license_open else 0.0 for _, q in pairs])
    share_machine = _mean([1.0 if ds.formats else 0.0 for ds, _ in pairs])
    share_theme = _mean([1.0 if ds.theme else 0.0 for ds, _ in pairs])
    share_explicit_lic = _mean(
        [1.0 if (q.license_open or ds.license_id) else 0.0 for ds, q in pairs]
    )
    mean_dcat = _mean([q.dcat_ap_it for _, q in pairs])
    share_hvd = _mean([1.0 if q.hvd_category else 0.0 for _, q in pairs])
    share_high_star = _mean([1.0 if q.stars_5 >= 3 else 0.0 for _, q in pairs])
    share_fresh = _mean(
        [1.0 if (q.freshness_days is not None and q.freshness_days <= 365) else 0.0 for _, q in pairs]
    )
    mean_composite = _mean([q.composite for _, q in pairs])
    coverage = min(1.0, n / 20.0)

    quality = round(mean_composite * 100, 1)
    portal = round(_mean([share_open_license, share_machine, share_theme, coverage]) * 100, 1)
    policy = round(_mean([share_explicit_lic, share_open_license, mean_dcat]) * 100, 1)
    impact = round(_mean([share_hvd, share_high_star, share_fresh]) * 100, 1)
    overall = round(
        w["policy"] * policy + w["portal"] * portal + w["quality"] * quality + w["impact"] * impact,
        1,
    )
    return DimensionScores(policy, portal, quality, impact, overall, odm_level(overall))


def build_recommendations(pairs: list[_Pair]) -> tuple[Recommendation, ...]:
    """Raccomandazioni azionabili dai gap aggregati dell'ente."""
    if not pairs:
        return (
            Recommendation(
                code="no_open_data", severity="alta", dimension="portal",
                message="L'ente non espone dataset su questo portale: pubblica i primi "
                "dataset in formato aperto con licenza CC BY.",
                affected_count=0,
            ),
        )
    n = len(pairs)
    recs: list[Recommendation] = []

    no_license = [ds for ds, q in pairs if not q.license_open]
    if len(no_license) / n > 0.2:
        recs.append(Recommendation(
            code="open_license", severity=_severity(len(no_license) / n), dimension="policy",
            message=f"Aggiungi una licenza aperta (es. CC BY 4.0) ai {len(no_license)} dataset senza licenza aperta.",
            affected_count=len(no_license),
        ))

    closed_fmt = [ds for ds, _ in pairs if not _has_open_format(ds)]
    if len(closed_fmt) / n > 0.3:
        recs.append(Recommendation(
            code="open_format", severity=_severity(len(closed_fmt) / n), dimension="quality",
            message=f"Pubblica in formati aperti (CSV/JSON/XML) i {len(closed_fmt)} dataset senza un formato aperto.",
            affected_count=len(closed_fmt),
        ))

    stale = [q for _, q in pairs if q.freshness_days is None or q.freshness_days > 365]
    if len(stale) / n > 0.4:
        recs.append(Recommendation(
            code="freshness", severity=_severity(len(stale) / n), dimension="quality",
            message=f"Aggiorna o dichiara la frequenza dei {len(stale)} dataset non aggiornati da oltre un anno.",
            affected_count=len(stale),
        ))

    low_dcat = [q for _, q in pairs if q.dcat_ap_it < 0.7]
    if len(low_dcat) / n > 0.3:
        recs.append(Recommendation(
            code="dcat_ap_it", severity=_severity(len(low_dcat) / n), dimension="policy",
            message=f"Completa i metadati DCAT-AP_IT (theme, publisher, frequenza) nei {len(low_dcat)} dataset incompleti.",
            affected_count=len(low_dcat),
        ))

    if not any(q.hvd_category for _, q in pairs):
        recs.append(Recommendation(
            code="hvd", severity="bassa", dimension="impact",
            message="Valuta la pubblicazione di dataset ad alto valore (HVD: mobilità, geospaziale, statistiche, ...).",
            affected_count=0,
        ))

    return tuple(recs)


def assess_entity(
    datasets: list[DatasetInput],
    *,
    weights: dict[str, float] | None = None,
    semantic: dict[str, float] | None = None,
    as_of: datetime | None = None,
) -> MaturityResult:
    """Valuta tutti i dataset di un ente e aggrega in una MaturityResult.

    `semantic` (opzionale): mappa dataset_id → semantic_clarity ∈ [0,1] (Haiku).
    """
    sem = semantic or {}
    pairs: list[_Pair] = []
    for ds in datasets:
        q = assess_quality(ds, semantic_clarity=sem.get(ds.id), as_of=as_of)
        pairs.append((ds, q))

    scores = score_dimensions(pairs, weights=weights)
    recommendations = build_recommendations(pairs)
    return MaturityResult(
        n_datasets=len(pairs),
        scores=scores,
        recommendations=recommendations,
        dataset_quality=tuple(q for _, q in pairs),
    )
