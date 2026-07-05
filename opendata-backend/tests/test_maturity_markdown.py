"""Test del builder Markdown embeddabile della scorecard di maturità.

Funzione pura: si testano i due scenari (dato sufficiente / insufficiente)
costruendo dict scorecard nella stessa forma di `build_scorecard`.
"""

from __future__ import annotations

from opendata_backend.maturity.markdown import build_scorecard_markdown

_UI = "https://opendata-ai.it"


def _scorecard_ok() -> dict:
    return {
        "entity": {"id": 7, "name": "Comune di Gioia del Colle", "type": "comune"},
        "assessed_at": "2026-06-29T10:00:00",
        "level": "Follower",
        "overall": 52.4,
        "dimensions": {"policy": 60.0, "portal": 48.0, "quality": 55.0, "impact": 46.5},
        "n_datasets": 24,
        "insufficient_data": False,
        "coverage": {"missing_core": [{"label": "Bilanci"}, {"label": "Mobilità"}]},
        "recommendations": [
            {"code": "Q1", "severity": "bassa", "message": "Aggiorna i metadati."},
            {"code": "P1", "severity": "alta", "message": "Pubblica i bilanci aperti."},
        ],
        "unmet_reuse_demand": {"count": 3, "items": [], "penalty": 0.1},
        "guida": None,
    }


def _scorecard_insufficiente(n: int = 0) -> dict:
    from opendata_core.maturity.guidance import build_guida_opendata

    return {
        "entity": {"id": 9, "name": "Comune di Esempio", "type": "comune"},
        "assessed_at": "2026-06-29T10:00:00",
        "level": "Dato insufficiente",
        "overall": 0.0,
        "dimensions": {"policy": 0.0, "portal": 0.0, "quality": 0.0, "impact": 0.0},
        "n_datasets": n,
        "insufficient_data": True,
        "guida": build_guida_opendata("Comune di Esempio", n_datasets=n),
    }


def test_markdown_sufficiente_riepilogo_e_link():
    md = build_scorecard_markdown(_scorecard_ok(), ui_base_url=_UI)
    assert "# Maturità Open Data — Comune di Gioia del Colle" in md
    assert "Livello ODM: Follower" in md
    assert "52.4/100" in md
    # 4 dimensioni in tabella
    assert "Qualità dei dati" in md and "55.0/100" in md
    # raccomandazione alta severità prima della bassa
    assert md.index("Pubblica i bilanci aperti") < md.index("Aggiorna i metadati")
    # settori mancanti + domanda di riuso
    assert "Bilanci" in md and "Mobilità" in md
    assert "Domanda di riuso non soddisfatta" in md
    # link assoluti alla scheda + attribuzione
    assert f"{_UI}/maturita" in md
    assert f"OpenData AI]({_UI})" in md
    # niente disclaimer "dato insufficiente"
    assert "Dato insufficiente" not in md


def test_markdown_insufficiente_disclaimer_vantaggi_e_docs():
    md = build_scorecard_markdown(_scorecard_insufficiente(0), ui_base_url=_UI)
    assert "Dato insufficiente" in md
    assert "non sono stati trovati open data" in md.lower()
    # vantaggi dell'open data
    assert "Perché pubblicare open data" in md
    assert "Trasparenza e fiducia" in md
    assert "Conformità normativa" in md
    # guida operativa passo-passo
    assert "Come partire — guida operativa" in md
    assert "Nomina il Responsabile" in md
    # link alla documentazione opendata-ai (guida + scheda)
    assert f"{_UI}/guida-open-data" in md
    assert f"{_UI}/maturita" in md
    # riferimenti istituzionali ufficiali
    assert "dati.gov.it" in md
    assert "DCAT-AP_IT" in md


def test_markdown_insufficiente_pochi_dataset_menziona_il_numero():
    md = build_scorecard_markdown(_scorecard_insufficiente(2), ui_base_url=_UI)
    assert "2 dataset valutabili" in md


def test_markdown_rispetta_base_url_custom():
    md = build_scorecard_markdown(_scorecard_ok(), ui_base_url="http://localhost:3000/")
    assert "http://localhost:3000/maturita" in md
    # nessun doppio slash dovuto alla trailing slash
    assert "localhost:3000//" not in md
