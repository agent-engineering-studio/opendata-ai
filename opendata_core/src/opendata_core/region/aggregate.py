"""Aggregazione regionale deterministica (#228).

Compone le sintesi-comune in una `RegionOverview`: distribuzione per stato
(riusando la macchina a stati #184), mediana ODM, copertura HVD regionale,
mediane per dimensione e i punti "dove intervenire". Nessun LLM, nessuna rete —
tutto derivato dai dati iniettati.
"""

from __future__ import annotations

from statistics import median

from opendata_core.dataplan.state import accompaniment_state
from opendata_core.maturity.coverage import HVD_LABELS

from .models import ComuneSummary, InterventionHint, RegionOverview

# Gli stati della macchina di accompagnamento (#184), in ordine di crescita.
_STATI = ("zero_dati", "pochi_dati", "in_crescita", "maturo")

# Un comune "necessita intervento" sotto questa soglia di maturità (allineata a
# _OVERALL_CRESCITA di dataplan.state: sotto 40 = follower/da accompagnare).
_SOGLIA_INTERVENTO = 40.0
# Una dimensione ODM è "debole" a livello regionale sotto questa mediana.
_SOGLIA_DIMENSIONE = 50.0

_MAX_COMUNI_HINT = 5
_MAX_DIMENSIONI_HINT = 3


def _median_or_none(values: list[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(float(median(vals)), 1) if vals else None


def _dove_intervenire(
    comuni: list[ComuneSummary], dimensioni_mediana: dict[str, float]
) -> list[InterventionHint]:
    hints: list[InterventionHint] = []

    # Comuni prioritari: prima quelli senza dati, poi i più deboli. I comuni
    # senza `overall` sono i più urgenti (overall trattato come -1 nel sort).
    def _key(c: ComuneSummary) -> tuple[int, float, str]:
        return (0 if c.overall is None else 1, c.overall if c.overall is not None else -1.0, c.istat)

    needing = [c for c in comuni if c.overall is None or c.overall < _SOGLIA_INTERVENTO]
    for c in sorted(needing, key=_key)[:_MAX_COMUNI_HINT]:
        if c.overall is None or c.n_dataset == 0:
            motivo = "nessun dato pubblicato"
        else:
            motivo = f"maturità bassa ({c.overall:.0f}/100)"
        hints.append(
            InterventionHint(
                tipo="comune", istat=c.istat, nome=c.nome, overall=c.overall, motivo=motivo
            )
        )

    # Dimensioni ODM deboli in regione (mediana sotto soglia), dalla più debole.
    weak = sorted(
        ((d, m) for d, m in dimensioni_mediana.items() if m < _SOGLIA_DIMENSIONE),
        key=lambda x: x[1],
    )
    for dim, med in weak[:_MAX_DIMENSIONI_HINT]:
        hints.append(
            InterventionHint(
                tipo="dimensione",
                dimensione=dim,
                mediana=med,
                motivo=f"dimensione debole in regione (mediana {med:.0f})",
            )
        )
    return hints


def aggregate_region(
    comuni: list[ComuneSummary],
    *,
    regione: str,
    cod_regione: str,
    comuni_totali: int | None = None,
) -> RegionOverview:
    """Vista d'insieme della regione a partire dalle sintesi-comune.

    `comuni_totali` (dall'anagrafica) può superare `len(comuni)` quando non tutti
    i comuni hanno una sintesi: i mancanti contano come `zero_dati`.
    """
    total = comuni_totali if comuni_totali is not None else len(comuni)

    distribuzione = {s: 0 for s in _STATI}
    for c in comuni:
        stato = accompaniment_state(n_dataset=c.n_dataset, overall=c.overall).stato
        distribuzione[stato] = distribuzione.get(stato, 0) + 1
    # Comuni della regione senza alcuna sintesi → zero dati.
    distribuzione["zero_dati"] += max(0, total - len(comuni))

    valutati = [c for c in comuni if c.overall is not None]
    mediana_overall = _median_or_none([c.overall for c in valutati])

    hvd_copertura = {
        cat: (round(sum(1 for c in comuni if cat in c.hvd_categorie) / total, 3) if total else 0.0)
        for cat in HVD_LABELS
    }

    dimensioni_keys = {k for c in comuni for k in c.dimensioni}
    dimensioni_mediana: dict[str, float] = {}
    for d in sorted(dimensioni_keys):
        m = _median_or_none([c.dimensioni.get(d) for c in comuni if d in c.dimensioni])
        if m is not None:
            dimensioni_mediana[d] = m

    return RegionOverview(
        regione=regione,
        cod_regione=cod_regione,
        comuni_totali=total,
        comuni_valutati=len(valutati),
        distribuzione_stato=distribuzione,
        mediana_overall=mediana_overall,
        hvd_copertura=hvd_copertura,
        dimensioni_mediana=dimensioni_mediana,
        dove_intervenire=_dove_intervenire(comuni, dimensioni_mediana),
    )
