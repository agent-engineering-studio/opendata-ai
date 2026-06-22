"""Aggregazione per ente: dimensioni 0–100, overall pesato, livello ODM, gap → raccomandazioni."""

from __future__ import annotations

from datetime import datetime

from .models import (
    DEFAULT_MIN_DATASETS,
    DEFAULT_WEIGHTS,
    INSUFFICIENT_LEVEL,
    OPEN_FORMATS,
    DatasetInput,
    DimensionBreakdown,
    DimensionScores,
    MaturityResult,
    QualityScore,
    Recommendation,
    odm_level,
)
from dataclasses import replace
from .coverage import HVD_LABELS, assess_coverage
from .models import CoverageResult
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


def _aggregate_shares(pairs: list[_Pair]) -> dict[str, float]:
    """Sotto-metriche aggregate (0–1) condivise da punteggio e breakdown."""
    n = len(pairs)
    return {
        "open_license": _mean([1.0 if q.license_open else 0.0 for _, q in pairs]),
        "machine": _mean([1.0 if ds.formats else 0.0 for ds, _ in pairs]),
        "open_format": _mean([1.0 if _has_open_format(ds) else 0.0 for ds, _ in pairs]),
        "theme": _mean([1.0 if ds.theme else 0.0 for ds, _ in pairs]),
        "explicit_lic": _mean([1.0 if (q.license_open or ds.license_id) else 0.0 for ds, q in pairs]),
        "dcat": _mean([q.dcat_ap_it for _, q in pairs]),
        "hvd": _mean([1.0 if q.hvd_category else 0.0 for _, q in pairs]),
        "high_star": _mean([1.0 if q.stars_5 >= 3 else 0.0 for _, q in pairs]),
        "fresh": _mean([1.0 if (q.freshness_days is not None and q.freshness_days <= 365) else 0.0 for _, q in pairs]),
        "fair": _mean([q.fair_mean for _, q in pairs]),
        "iso": _mean([q.iso25012 for _, q in pairs]),
        "stars_norm": _mean([q.stars_5 / 5.0 for _, q in pairs]),
        "composite": _mean([q.composite for _, q in pairs]),
        "portal_coverage": min(1.0, n / 20.0),
    }


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

    s = _aggregate_shares(pairs)
    quality = round(s["composite"] * 100, 1)
    portal = round(_mean([s["open_license"], s["machine"], s["theme"], s["portal_coverage"]]) * 100, 1)
    policy = round(_mean([s["explicit_lic"], s["open_license"], s["dcat"]]) * 100, 1)
    impact_base = _mean([s["hvd"], s["high_star"], s["fresh"]]) * 100
    penalty = max(0.0, min(1.0, reuse_demand_penalty))
    impact = round(impact_base * (1.0 - penalty), 1)
    overall = round(
        w["policy"] * policy + w["portal"] * portal + w["quality"] * quality + w["impact"] * impact,
        1,
    )
    return DimensionScores(policy, portal, quality, impact, overall, odm_level(overall))


# Cosa misura ciascuna dimensione + le sue sotto-metriche (etichetta → chiave share).
_DIM_META: dict[str, tuple[str, str, list[tuple[str, str]]]] = {
    "policy": (
        "Policy",
        "Governance del dato: licenze aperte esplicite e metadati DCAT-AP_IT — la "
        "base che rende i dataset legalmente riutilizzabili e trovabili sul catalogo nazionale.",
        [("Licenza esplicita", "explicit_lic"), ("Licenza aperta", "open_license"),
         ("Metadati DCAT-AP_IT", "dcat")],
    ),
    "portal": (
        "Portale",
        "Presenza sul portale: ampiezza del catalogo e quanto i dataset sono "
        "indicizzati (tema), accessibili e in formati strutturati.",
        [("Licenza aperta", "open_license"), ("Formati strutturati", "machine"),
         ("Tema indicizzato", "theme"), ("Ampiezza catalogo", "portal_coverage")],
    ),
    "quality": (
        "Qualità",
        "Qualità intrinseca dei dataset: scala a stelle (Berners-Lee), FAIR, "
        "completezza DCAT e ISO/IEC 25012 (completezza, attualità, coerenza).",
        [("Stelle (5-star)", "stars_norm"), ("FAIR", "fair"),
         ("Metadati DCAT-AP_IT", "dcat"), ("ISO/IEC 25012", "iso")],
    ),
    "impact": (
        "Impatto",
        "Impatto e riuso: dataset ad alto valore (HVD), apertura ≥3 stelle e "
        "attualità — quanto i dati si trasformano in servizi e valore per il territorio.",
        [("Dataset ad alto valore (HVD)", "hvd"), ("Aperti ≥3 stelle", "high_star"),
         ("Aggiornati nell'ultimo anno", "fresh")],
    ),
}


def build_breakdown(
    pairs: list[_Pair], scores: DimensionScores
) -> tuple[DimensionBreakdown, ...]:
    """Spiega ciascuna dimensione: cosa misura, sotto-metriche (0–100, dalla più
    debole) e le 1–3 voci sotto soglia che la trainano in basso."""
    if not pairs:
        return ()
    s = _aggregate_shares(pairs)
    out: list[DimensionBreakdown] = []
    for dim, (label, desc, submetrics) in _DIM_META.items():
        drivers = sorted(
            ((lbl, round(s[key] * 100, 1)) for lbl, key in submetrics),
            key=lambda kv: kv[1],
        )
        weakest = tuple(lbl for lbl, val in drivers if val < 70.0)[:3]
        out.append(DimensionBreakdown(
            dimension=dim, label=label, score=getattr(scores, dim),
            description=desc, drivers=tuple(drivers), weakest=weakest,
        ))
    return tuple(out)


def _coverage_recommendations(coverage: CoverageResult) -> list[Recommendation]:
    """Gap di copertura tematica → settori mancanti e categorie HVD assenti."""
    recs: list[Recommendation] = []
    missing = coverage.missing_core
    if missing:
        names = ", ".join(s.label for s in missing[:4])
        n_core = sum(1 for s in coverage.sectors if s.is_core)
        gap_ratio = len(missing) / n_core if n_core else 0.0
        recs.append(Recommendation(
            code="sector_gap", severity=_severity(gap_ratio), dimension="portal",
            message=f"Per una collection ottimale di un ente di tipo «{coverage.entity_type}» "
            f"mancano dataset in {len(missing)} settori chiave su {n_core}: {names}. "
            "Sono gli ambiti più attesi e a maggior domanda di riuso: pianifica la "
            "pubblicazione partendo da quelli a priorità più alta.",
            affected_count=len(missing),
        ))
    # HVD: distinguiamo "nessuna categoria" (gestita altrove come 'hvd') dalla
    # copertura parziale, dove ha senso indicare quali categorie aggiungere.
    if coverage.hvd_present and coverage.hvd_missing:
        names = ", ".join(HVD_LABELS.get(h, h) for h in coverage.hvd_missing)
        recs.append(Recommendation(
            code="hvd_coverage", severity="bassa", dimension="impact",
            message=f"Coperte {len(coverage.hvd_present)} delle 6 categorie di dati ad "
            f"elevato valore (HVD); mancano: {names}. Completare le categorie HVD è la "
            "leva con il maggior ritorno di riuso e impatto economico (Reg. UE 2023/138).",
            affected_count=len(coverage.hvd_missing),
        ))
    return recs


def build_recommendations(
    pairs: list[_Pair], coverage: CoverageResult | None = None
) -> tuple[Recommendation, ...]:
    """Raccomandazioni azionabili dai gap aggregati dell'ente.

    Se `coverage` è fornito, aggiunge i gap di copertura tematica (settori core
    mancanti) e HVD parziale — i gap "di collection", oltre a quelli "di qualità".
    """
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

    if coverage is not None:
        recs.extend(_coverage_recommendations(coverage))

    return tuple(recs)


def assess_entity(
    datasets: list[DatasetInput],
    *,
    weights: dict[str, float] | None = None,
    semantic: dict[str, float] | None = None,
    as_of: datetime | None = None,
    reuse_demand_penalty: float = 0.0,
    min_datasets: int = DEFAULT_MIN_DATASETS,
    entity_type: str | None = None,
    coverage_templates: dict[str, dict[str, int]] | None = None,
) -> MaturityResult:
    """Valuta tutti i dataset di un ente e aggrega in una MaturityResult.

    `semantic` (opzionale): mappa dataset_id → semantic_clarity ∈ [0,1] (Haiku).
    `reuse_demand_penalty` ∈ [0,1]: penalità Impact da domanda di riuso non soddisfatta.
    `min_datasets`: sotto soglia → insufficient_data=True e livello "Dato insufficiente"
    (no punteggi falsi su basi troppo piccole).
    `entity_type` (opzionale): tipo di ente (comune/regione/provincia/ente) per
    valutare la copertura tematica rispetto alla collection ottimale attesa.
    `coverage_templates`: override iniettabile dei template di copertura.
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
    coverage = assess_coverage(
        datasets, entity_type=entity_type, templates=coverage_templates
    ) if datasets else None
    recommendations = build_recommendations(pairs, coverage)
    breakdown = build_breakdown(pairs, scores)
    return MaturityResult(
        n_datasets=len(pairs),
        scores=scores,
        recommendations=recommendations,
        dataset_quality=tuple(q for _, q in pairs),
        insufficient_data=insufficient,
        coverage=coverage,
        breakdown=breakdown,
    )
