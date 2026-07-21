"""Test del catalogo dataset candidati del Copilota Open Data (#172, D1)."""

from __future__ import annotations

import pytest

from opendata_core.dataplan import CandidateDataset, catalog_by_area, load_catalog
from opendata_core.dataplan import catalog as catalog_mod
from opendata_core.dataplan.models import HVD_CATEGORIES


def test_catalog_loads_and_is_valid() -> None:
    cat = load_catalog()
    assert len(cat) >= 12
    assert all(isinstance(c, CandidateDataset) for c in cat)
    # id univoci
    ids = [c.id for c in cat]
    assert len(ids) == len(set(ids))
    # ogni hvd dichiarato è una categoria valida (o None)
    assert all(c.hvd is None or c.hvd in HVD_CATEGORIES for c in cat)
    # privacy/sforzo negli enum
    assert all(c.privacy in ("nullo", "aggregato", "personale") for c in cat)
    assert all(c.sforzo in ("basso", "medio", "alto") for c in cat)


def test_gia_aperto_populated_for_national_obligations() -> None:
    by_id = {c.id: c for c in load_catalog()}
    # gli adempimenti nazionali hanno la fonte "già aperto altrove"
    assert by_id["bilancio-siope"].gia_aperto is not None
    assert "BDAP" in by_id["bilancio-siope"].gia_aperto.fonte
    assert by_id["appalti-anac"].gia_aperto is not None
    assert by_id["progetti-pnrr-coesione"].gia_aperto is not None
    # un dato puramente locale NON è già aperto altrove
    assert by_id["rifiuti-differenziata"].gia_aperto is None


def test_sblocca_and_privacy_families_present() -> None:
    by_id = {c.id: c for c in load_catalog()}
    # il PUG sblocca la riconciliazione suolo (segnale di riuso, per D2)
    assert any("suolo" in s.lower() for s in by_id["pug-zonizzazione"].sblocca)
    # esistono dati con privacy "personale" (→ de-identificazione, D4)
    assert any(c.privacy == "personale" for c in load_catalog())
    # e adempimenti a sforzo basso (quick-win, per D2)
    assert by_id["bilancio-siope"].sforzo == "basso"


def test_catalog_by_area() -> None:
    grouped = catalog_by_area()
    assert "SIT" in grouped and "Ambiente" in grouped
    assert any(c.id == "pug-zonizzazione" for c in grouped["SIT"])


def test_env_override_and_validation(tmp_path, monkeypatch) -> None:
    # override del percorso + validazione fail-fast su HVD non valida
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "candidati:\n  - id: x\n    nome: X\n    area: A\n    fonte_interna: f\n"
        "    descrizione: d\n    hvd: non_esiste\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DATAPLAN_CATALOG_PATH", str(bad))
    catalog_mod.clear_cache()
    with pytest.raises(ValueError, match="HVD"):
        load_catalog()
    catalog_mod.clear_cache()  # ripristina per gli altri test


def test_duplicate_ids_rejected(tmp_path, monkeypatch) -> None:
    dup = tmp_path / "dup.yaml"
    dup.write_text(
        "candidati:\n"
        "  - {id: a, nome: A, area: X, fonte_interna: f, descrizione: d}\n"
        "  - {id: a, nome: B, area: Y, fonte_interna: g, descrizione: e}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DATAPLAN_CATALOG_PATH", str(dup))
    catalog_mod.clear_cache()
    with pytest.raises(ValueError, match="duplicati"):
        load_catalog()
    catalog_mod.clear_cache()
