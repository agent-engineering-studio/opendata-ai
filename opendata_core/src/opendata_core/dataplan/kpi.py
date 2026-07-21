"""KPI del pilota + snapshot plannabile (#187, D16 di #170).

Motore **puro e deterministico**: dal piano prioritizzato (D2) calcola i KPI
*plannabili* (quelli derivabili senza dati di runtime) e li confronta col target
del pilota. I KPI di runtime (dataset pubblicati/conformi, download a 3 mesi,
ore-uomo risparmiate) NON si inventano qui: sono definiti con metodo nel doc
`docs/dataplan-pilot-kpi.md` e misurati a valle.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel

from .prioritize import RankedCandidate

#: Target del pilota (§8 della guida): ≥10 dataset conformi in ≤8 settimane,
#: senza un data team.
TARGET_DATASET_CONFORMI = 10
TARGET_SETTIMANE = 8


class PlanKpi(BaseModel):
    """KPI plannabili di un piano (baseline t0 del percorso)."""

    dataset_nel_piano: int
    quick_win: int
    gia_aperti_nazionali: int   # dataset che basta linkare (zero produzione)
    da_produrre: int            # quick win locali (produzione facile)
    hvd_coperti_nel_lotto: int  # categorie HVD distinte nel lotto quick-win
    hvd_categorie_lotto: list[str]
    pct_aggiornamento_automatico: float | None  # None se non è dato l'insieme monitorato
    target_dataset_conformi: int = TARGET_DATASET_CONFORMI
    target_settimane: int = TARGET_SETTIMANE
    target_raggiungibile_dal_lotto: bool = False


def plan_kpi(
    ranked: Iterable[RankedCandidate], *, monitored_ids: Iterable[str] | None = None,
) -> PlanKpi:
    """Calcola i KPI plannabili dal piano prioritizzato. Deterministico."""
    items = list(ranked)
    quick = [r for r in items if r.quadrante == "quick_win"]
    gia_aperti = [r for r in quick if r.candidate.gia_aperto is not None]
    da_produrre = [r for r in quick if r.candidate.gia_aperto is None]
    hvd_lotto = sorted({r.candidate.hvd for r in quick if r.candidate.hvd})
    monitored = set(monitored_ids) if monitored_ids is not None else None
    pct_auto: float | None = None
    if monitored is not None and items:
        coperti = sum(1 for r in items if r.candidate.id in monitored)
        pct_auto = round(100 * coperti / len(items), 1)
    return PlanKpi(
        dataset_nel_piano=len(items),
        quick_win=len(quick),
        gia_aperti_nazionali=len(gia_aperti),
        da_produrre=len(da_produrre),
        hvd_coperti_nel_lotto=len(hvd_lotto),
        hvd_categorie_lotto=hvd_lotto,
        pct_aggiornamento_automatico=pct_auto,
        # il lotto quick-win basta a raggiungere il target di dataset conformi?
        target_raggiungibile_dal_lotto=len(quick) >= TARGET_DATASET_CONFORMI,
    )
