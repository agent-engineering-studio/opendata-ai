"""Test delle regole privacy/GDPR del Copilota Open Data (#175, D4)."""

from __future__ import annotations

from opendata_core.dataplan import (
    CandidateDataset,
    all_families,
    checklist_for,
    family_for,
    load_catalog,
    rules_for,
)


def _cand(id_: str, area: str, privacy: str = "nullo", nome: str | None = None) -> CandidateDataset:
    return CandidateDataset(
        id=id_, nome=nome or id_, area=area, fonte_interna="f",
        descrizione="d", privacy=privacy,
    )


def test_family_mapping_and_suap_disambiguation() -> None:
    assert family_for(_cand("t", "Tributi")) == "tributi"
    assert family_for(_cand("a", "Anagrafe")) == "anagrafe"
    assert family_for(_cand("x", "Ambiente")) == "generico"
    # SUAP/SUE disambiguata per keyword
    assert family_for(_cand("edilizia-pratiche-sue", "SUAP/SUE", nome="Edilizia")) == "edilizia_sue"
    assert family_for(_cand("esercizi-commerciali", "SUAP/SUE", nome="Esercizi")) == "commercio_suap"


def test_rules_for_is_failsafe() -> None:
    # famiglia sconosciuta → generico (mai KeyError)
    assert rules_for("boh").famiglia == "generico"
    assert rules_for("sociale").k_anonimato == 10  # categoria sensibile: soglia più alta


def test_generico_no_human_gate() -> None:
    cl = checklist_for(_cand("rifiuti", "Ambiente", privacy="nullo"))
    assert cl.famiglia == "generico"
    assert cl.richiede_validazione_umana is False
    assert cl.k_anonimato == 1
    assert any("senza gate DPO" in p for p in cl.passi)


def test_personal_data_forces_human_validation() -> None:
    # vincolo §7: dato personale → validazione umana sempre
    cl = checklist_for(_cand("edilizia", "SUAP/SUE", privacy="personale", nome="Edilizia"))
    assert cl.richiede_validazione_umana is True
    assert cl.famiglia == "edilizia_sue"
    assert any("richiedente" in c for c in cl.campi_da_rimuovere)
    assert any("DPO" in p for p in cl.passi)


def test_aggregato_thresholds_and_steps() -> None:
    cl = checklist_for(_cand("tari", "Tributi", privacy="aggregato"))
    assert cl.k_anonimato == 5
    assert "zona" in cl.granularita_minima.lower()
    assert any("k-anonimato" in p for p in cl.passi)
    assert any("codice_fiscale" in c for c in cl.campi_da_rimuovere)


def test_all_catalog_candidates_get_a_checklist() -> None:
    # ogni candidato del catalogo produce una checklist coerente; i "personale"
    # richiedono sempre validazione umana
    for c in load_catalog():
        cl = checklist_for(c)
        assert cl.famiglia in all_families()
        if c.privacy == "personale":
            assert cl.richiede_validazione_umana is True
