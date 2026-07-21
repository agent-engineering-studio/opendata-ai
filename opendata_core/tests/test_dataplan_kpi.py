"""Test dei KPI plannabili del pilota (#187, D16)."""

from __future__ import annotations

from opendata_core.dataplan import load_catalog, plan_kpi, prioritize
from opendata_core.dataplan.kpi import TARGET_DATASET_CONFORMI


def test_plan_kpi_structure() -> None:
    k = plan_kpi(prioritize(load_catalog()))
    assert k.dataset_nel_piano == len(load_catalog())
    assert k.quick_win >= 1
    # il lotto quick-win si divide in "già aperti" (link) + "da produrre"
    assert k.gia_aperti_nazionali + k.da_produrre == k.quick_win
    assert k.gia_aperti_nazionali >= 3        # BDAP/ANAC/OpenPNRR/ISTAT/ISPRA
    # HVD coperti nel lotto: categorie distinte, non vuote
    assert k.hvd_coperti_nel_lotto == len(k.hvd_categorie_lotto) >= 1
    assert k.target_dataset_conformi == TARGET_DATASET_CONFORMI


def test_pct_aggiornamento_automatico() -> None:
    ranked = prioritize(load_catalog())
    # senza insieme monitorato → None (onesto)
    assert plan_kpi(ranked).pct_aggiornamento_automatico is None
    # con un sottoinsieme monitorato → percentuale sul totale del piano
    monitored = {"rifiuti-differenziata", "bilancio-siope"}
    k = plan_kpi(ranked, monitored_ids=monitored)
    assert k.pct_aggiornamento_automatico is not None
    assert 0 < k.pct_aggiornamento_automatico < 100


def test_target_reachable_flag() -> None:
    # catalogo attuale: 7 quick win < target 10 → non raggiungibile dal solo lotto
    k = plan_kpi(prioritize(load_catalog()))
    assert k.target_raggiungibile_dal_lotto == (k.quick_win >= TARGET_DATASET_CONFORMI)
