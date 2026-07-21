"""Test di Politica Open Data + Piano di pubblicazione del Copilota (#174, D3)."""

from __future__ import annotations

from opendata_core.dataplan import (
    build_piano,
    build_politica,
    load_catalog,
    prioritize,
    render_piano_markdown,
    render_politica_markdown,
)
from opendata_core.quality import validate_dcat


def _piano():
    return build_piano(prioritize(load_catalog()), ente="Gioia del Colle")


def test_piano_voci_and_quick_win() -> None:
    pl = _piano()
    assert pl.ente == "Gioia del Colle"
    assert len(pl.voci) == len(load_catalog())
    # il lotto quick-win non è vuoto e coincide col quadrante
    assert pl.quick_win
    assert {v.candidate_id for v in pl.voci if v.quadrante == "quick_win"} == set(pl.quick_win)
    # cadenza + ufficio popolati per ogni voce
    assert all(v.cadenza and v.ufficio and v.licenza for v in pl.voci)
    # l'ordine del piano riflette la prioritizzazione (prima voce = quick win)
    assert pl.voci[0].quadrante == "quick_win"


def test_piano_dcat_is_valid_and_precompiled() -> None:
    pl = _piano()
    v = next(v for v in pl.voci if v.candidate_id == "rifiuti-differenziata")
    meta = v.metadati_dcat
    # titolo/descrizione deducibili sono compilati; ente/licenza presenti
    assert meta["dataset"]["dct:title"] == v.nome
    assert meta["dataset"]["dct:license"] == v.licenza
    assert meta["dataset"]["dct:publisher"]["foaf:name"] == "Gioia del Colle"
    # scheda DCAT-AP_IT strutturalmente valida (nessuna segnalazione "alta")
    assert validate_dcat(meta)["valido"] is True
    # i campi editoriali non deducibili restano tracciati come mancanti
    assert isinstance(v.campi_dcat_mancanti, list)


def test_politica_structure_and_licenza() -> None:
    p = build_politica(ente="Gioia del Colle")
    titoli = [s.titolo for s in p.sezioni]
    assert any("Finalità" in t for t in titoli)
    assert any("Ruoli" in t for t in titoli)
    assert any("Licenza" in t for t in titoli)
    # licenza consigliata + riferimenti normativi chiave nel testo
    testo = " ".join(s.testo for s in p.sezioni)
    assert "CC-BY-4.0" in testo and "AGID" in testo and "GDPR" in testo
    assert "Gioia del Colle" in p.titolo


def test_markdown_rendering() -> None:
    md_pol = render_politica_markdown(build_politica(ente="X"))
    assert md_pol.startswith("# Politica Open Data del Comune di X")
    md_piano = render_piano_markdown(_piano())
    assert "Piano di pubblicazione" in md_piano and "| Priorità |" in md_piano


def test_custom_licenza_propagates() -> None:
    pl = build_piano(prioritize(load_catalog()), ente="X", licenza="IODL-2.0")
    assert pl.licenza == "IODL-2.0"
    assert all(v.licenza == "IODL-2.0" for v in pl.voci)
    assert build_politica(ente="X", licenza="IODL-2.0").licenza == "IODL-2.0"
