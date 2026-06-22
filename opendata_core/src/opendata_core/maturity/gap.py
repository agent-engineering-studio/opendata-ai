"""Gap analysis maturità — dalla scorecard al "cosa fare e in che direzione" (#50).

Layer ADDITIVO sopra l'assessment esistente (`DimensionScores` + `Recommendation`
+ pesi/livelli ODM): non re-misura nulla, ma risponde a "quanto manca al livello
successivo, qual è il collo di bottiglia, cosa conviene fare PER PRIMO". Le
raccomandazioni già prodotte vengono classificate **quick-win** (correzioni rapide
sui dataset esistenti: licenza, metadati DCAT-AP_IT, formato aperto, aggiornamento)
vs **strategico** (richiede di pubblicare nuovi dataset / coprire settori/HVD) e
ordinate in una roadmap. Pure Python, deterministico.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import (
    DEFAULT_ODM_LEVELS,
    DEFAULT_WEIGHTS,
    DimensionScores,
    Recommendation,
)

DIM_LABELS = {
    "policy": "Politiche e licenze",
    "portal": "Portale e pubblicazione",
    "quality": "Qualità dei dati",
    "impact": "Impatto e riuso",
}

# Codici raccomandazione → sforzo. Quick-win = si correggono i dataset GIÀ
# pubblicati (veloce); strategico = serve produrre/pubblicare nuovi dati.
_QUICK_WIN_CODES = {"open_license", "dcat_ap_it", "open_format", "freshness"}

_SEV_ORDER = {"alta": 0, "media": 1, "bassa": 2}


@dataclass(frozen=True)
class AzioneGap:
    code: str
    dimension: str
    severity: str
    tipo: str  # "quick_win" | "strategico"
    messaggio: str
    affected_count: int
    sul_collo_di_bottiglia: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "dimension": self.dimension,
            "dimension_label": DIM_LABELS.get(self.dimension, self.dimension),
            "severity": self.severity,
            "tipo": self.tipo,
            "messaggio": self.messaggio,
            "affected_count": self.affected_count,
            "sul_collo_di_bottiglia": self.sul_collo_di_bottiglia,
        }


@dataclass(frozen=True)
class GapAnalysis:
    livello_attuale: str
    prossimo_livello: str | None          # None se già al livello massimo
    punti_al_prossimo: float | None       # punti overall mancanti al prossimo livello
    collo_di_bottiglia: str               # dimensione (code) che frena di più l'overall
    collo_di_bottiglia_label: str
    azioni: tuple[AzioneGap, ...]         # ordinate: quick-win → strategico, sul collo prima

    @property
    def quick_win(self) -> tuple[AzioneGap, ...]:
        return tuple(a for a in self.azioni if a.tipo == "quick_win")

    @property
    def strategiche(self) -> tuple[AzioneGap, ...]:
        return tuple(a for a in self.azioni if a.tipo == "strategico")

    def as_dict(self) -> dict[str, Any]:
        return {
            "livello_attuale": self.livello_attuale,
            "prossimo_livello": self.prossimo_livello,
            "punti_al_prossimo": self.punti_al_prossimo,
            "collo_di_bottiglia": self.collo_di_bottiglia,
            "collo_di_bottiglia_label": self.collo_di_bottiglia_label,
            "azioni": [a.as_dict() for a in self.azioni],
            "quick_win": [a.as_dict() for a in self.quick_win],
            "strategiche": [a.as_dict() for a in self.strategiche],
        }


def analyze_gaps(
    scores: DimensionScores,
    recommendations: tuple[Recommendation, ...],
    *,
    weights: dict[str, float] | None = None,
    levels: list[tuple[float, str]] | None = None,
) -> GapAnalysis:
    """Costruisce la gap analysis da scorecard + raccomandazioni esistenti."""
    w = weights or DEFAULT_WEIGHTS
    lv = sorted(levels or DEFAULT_ODM_LEVELS)

    # prossimo livello + punti mancanti sull'overall
    prossimo_livello: str | None = None
    punti_al_prossimo: float | None = None
    for soglia, nome in lv:
        if soglia > scores.overall:
            prossimo_livello = nome
            punti_al_prossimo = round(soglia - scores.overall, 1)
            break

    # collo di bottiglia: la dimensione dove sono recuperabili PIÙ punti di overall
    # (peso × distanza da 100). Migliorarla è la leva che alza di più il punteggio.
    dim_scores = {
        "policy": scores.policy, "portal": scores.portal,
        "quality": scores.quality, "impact": scores.impact,
    }
    collo = max(dim_scores, key=lambda d: w.get(d, 0.0) * (100.0 - dim_scores[d]))

    azioni = [
        AzioneGap(
            code=r.code,
            dimension=r.dimension,
            severity=r.severity,
            tipo="quick_win" if r.code in _QUICK_WIN_CODES else "strategico",
            messaggio=r.message,
            affected_count=r.affected_count,
            sul_collo_di_bottiglia=(r.dimension == collo),
        )
        for r in recommendations
    ]
    # ordine roadmap: prima i quick-win, poi gli strategici; dentro, prima quelle
    # sul collo di bottiglia, poi per gravità.
    azioni.sort(key=lambda a: (
        0 if a.tipo == "quick_win" else 1,
        0 if a.sul_collo_di_bottiglia else 1,
        _SEV_ORDER.get(a.severity, 3),
    ))

    return GapAnalysis(
        livello_attuale=scores.level,
        prossimo_livello=prossimo_livello,
        punti_al_prossimo=punti_al_prossimo,
        collo_di_bottiglia=collo,
        collo_di_bottiglia_label=DIM_LABELS.get(collo, collo),
        azioni=tuple(azioni),
    )
