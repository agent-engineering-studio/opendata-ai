"""Aggregazione per ente: dimensioni 0–100, overall pesato, livello ODM, gap → raccomandazioni."""

from __future__ import annotations

from datetime import datetime

from .models import (
    DEFAULT_MIN_DATASETS,
    DEFAULT_WEIGHTS,
    INSUFFICIENT_LEVEL,
    OPEN_FORMATS,
    DatasetInput,
    DimensionScores,
    MaturityResult,
    QualityScore,
    Recommendation,
    odm_level,
)
from dataclasses import replace
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
    pairs: list[_Pair], *, weights: dict[str, float] | None = None,
    reuse_demand_penalty: float = 0.0,
) -> DimensionScores:
    """Calcola le 4 dimensioni (0–100), l'overall pesato e il livello ODM.

    `reuse_demand_penalty` ∈ [0,1] (anello valore⇄maturità): la domanda di riuso non
    soddisfatta — i gap di dato rilevati nei report Territorio — riduce l'Impact.
    """
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
    impact_base = _mean([share_hvd, share_high_star, share_fresh]) * 100
    penalty = max(0.0, min(1.0, reuse_demand_penalty))
    impact = round(impact_base * (1.0 - penalty), 1)
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
                message="L'ente non espone ancora dataset aperti su questo portale. È il "
                "punto di partenza, non un giudizio: pubblica i primi dataset che già "
                "produci (bilanci, tributi, mobilità, servizi) in formato aperto e "
                "machine-readable (CSV/JSON), con una licenza CC BY 4.0, così cittadini "
                "e imprese possono iniziare a riutilizzarli.",
                affected_count=0,
            ),
        )
    n = len(pairs)
    recs: list[Recommendation] = []

    no_license = [ds for ds, q in pairs if not q.license_open]
    if len(no_license) / n > 0.2:
        k = len(no_license)
        recs.append(Recommendation(
            code="open_license", severity=_severity(k / n), dimension="policy",
            message=f"{k} dei {n} dataset non dichiarano una licenza aperta riconosciuta. "
            "Senza una licenza chiara (CC BY 4.0 o IODL 2.0) il riuso non è legalmente "
            "possibile anche quando il file è scaricabile: assegna a ciascuno una licenza "
            "aperta esplicita per sbloccarne davvero il riutilizzo da parte di terzi.",
            affected_count=k,
        ))

    closed_fmt = [ds for ds, _ in pairs if not _has_open_format(ds)]
    if len(closed_fmt) / n > 0.3:
        k = len(closed_fmt)
        recs.append(Recommendation(
            code="open_format", severity=_severity(k / n), dimension="quality",
            message=f"{k} dataset sono disponibili solo in formati chiusi o non strutturati "
            "(es. PDF o pagine web). Per essere elaborati da software e riusati vanno offerti "
            "anche in formati aperti e machine-readable — CSV, JSON o XML — accanto "
            "all'eventuale versione originale.",
            affected_count=k,
        ))

    stale = [q for _, q in pairs if q.freshness_days is None or q.freshness_days > 365]
    if len(stale) / n > 0.4:
        k = len(stale)
        recs.append(Recommendation(
            code="freshness", severity=_severity(k / n), dimension="quality",
            message=f"{k} dataset non risultano aggiornati da oltre un anno o non dichiarano "
            "una frequenza di aggiornamento. Un dato fermo perde valore e affidabilità: "
            "aggiornali e indica nei metadati la cadenza prevista (es. mensile, annuale), "
            "così chi li usa sa quanto sono attuali.",
            affected_count=k,
        ))

    low_dcat = [q for _, q in pairs if q.dcat_ap_it < 0.7]
    if len(low_dcat) / n > 0.3:
        k = len(low_dcat)
        recs.append(Recommendation(
            code="dcat_ap_it", severity=_severity(k / n), dimension="policy",
            message=f"{k} dataset hanno metadati DCAT-AP_IT incompleti: mancano spesso il tema, "
            "l'ente titolare o la frequenza di aggiornamento. Metadati completi rendono i dati "
            "trovabili sul catalogo nazionale e interoperabili tra enti: completa i campi "
            "obbligatori del profilo italiano per ciascun dataset.",
            affected_count=k,
        ))

    if not any(q.hvd_category for _, q in pairs):
        recs.append(Recommendation(
            code="hvd", severity="bassa", dimension="impact",
            message="Nessun dataset rientra nelle categorie a elevato valore (HVD): mobilità, "
            "geospaziale, ambiente, statistiche, società e imprese. Sono i dati che generano "
            "più riuso e impatto economico secondo il regolamento UE: valutarne la "
            "pubblicazione è la leva con il maggior ritorno per il territorio.",
            affected_count=0,
        ))

    return tuple(recs)


def assess_entity(
    datasets: list[DatasetInput],
    *,
    weights: dict[str, float] | None = None,
    semantic: dict[str, float] | None = None,
    as_of: datetime | None = None,
    reuse_demand_penalty: float = 0.0,
    min_datasets: int = DEFAULT_MIN_DATASETS,
) -> MaturityResult:
    """Valuta tutti i dataset di un ente e aggrega in una MaturityResult.

    `semantic` (opzionale): mappa dataset_id → semantic_clarity ∈ [0,1] (Haiku).
    `reuse_demand_penalty` ∈ [0,1]: penalità Impact da domanda di riuso non soddisfatta.
    `min_datasets`: sotto soglia → insufficient_data=True e livello "Dato insufficiente"
    (no punteggi falsi su basi troppo piccole).
    """
    sem = semantic or {}
    pairs: list[_Pair] = []
    for ds in datasets:
        q = assess_quality(ds, semantic_clarity=sem.get(ds.id), as_of=as_of)
        pairs.append((ds, q))

    scores = score_dimensions(pairs, weights=weights, reuse_demand_penalty=reuse_demand_penalty)
    insufficient = len(pairs) < min_datasets
    if insufficient:
        scores = replace(scores, level=INSUFFICIENT_LEVEL)
    recommendations = build_recommendations(pairs)
    return MaturityResult(
        n_datasets=len(pairs),
        scores=scores,
        recommendations=recommendations,
        dataset_quality=tuple(q for _, q in pairs),
        insufficient_data=insufficient,
    )
