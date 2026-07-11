"""Test del motore di riconciliazione suolo (#127, Parte V Fase 1)."""

from __future__ import annotations

from opendata_core.ispra.models import HazardSlice, LandCoverInfo, RiskIndicators
from opendata_core.landscape.models import LandscapeConstraint
from opendata_core.landuse import SoilRecord, reconcile_polygon
from opendata_core.sin_sir.models import ContaminationInfo


def _cont(*, contaminato: bool, sin: bool, sir_cont: int = 0) -> ContaminationInfo:
    return ContaminationInfo(
        contaminato=contaminato, sin=sin, sir_procedimenti=sir_cont, sir_contaminati=sir_cont,
        source_url="u", licenza="MOSAICO",
    )


def _paes(*, vincolato: bool, tutele: tuple[str, ...] = ()) -> LandscapeConstraint:
    return LandscapeConstraint(
        vincolato=vincolato, tutele=list(tutele), regione="Puglia",
        source_url="u", licenza="PPTR",
    )


def _lc(*, macro: int) -> LandCoverInfo:
    return LandCoverInfo(
        clc_code=f"{macro}11", macroclasse=macro,
        descrizione="test", impermeabilizzato=(macro == 1),
        source_url="u", licenza="ISPRA CLC",
    )

_OSM_DISMESSO = {
    "osm_type": "way", "osm_id": 42, "name": "Ex fornace",
    "kind": "brownfield", "area_mq": 12000, "url": "https://osm.org/way/42",
}


def _idrogeo(*, frane_p3p4_pct: float | None = None, idraulica: list[str] | None = None) -> RiskIndicators:
    return RiskIndicators(
        cod_comune="072021", nome="Test",
        frane_p3p4=HazardSlice(classe="p3p4", area_pct=frane_p3p4_pct) if frane_p3p4_pct else None,
        idraulica=[HazardSlice(classe=c, area_pct=1.0) for c in (idraulica or [])],
        source_url="https://idrogeo.example/pir/comuni/072021", licenza="CC BY",
    )


def test_solo_tag_osm_confidenza_bassa() -> None:
    # nessuna fonte oltre al tag → Bassa + campi mancanti a "da verificare"
    r = reconcile_polygon(osm_feature=_OSM_DISMESSO)
    assert isinstance(r, SoilRecord)
    assert r.confidenza == "Bassa"
    assert r.classificazione == "DISMESSO"
    assert r.vincoli == "da verificare"
    assert r.uso_reale == "da verificare" and r.destinazione_pug == "da verificare"
    assert any("Copernicus" in c for c in r.caveat)
    assert any("IdroGEO" in c for c in r.caveat)


def test_due_fonti_concordi_confidenza_alta() -> None:
    # tag OSM dismesso + vincolo IdroGEO → 2 fonti concordi → Alta, classificazione VINCOLATO
    r = reconcile_polygon(osm_feature=_OSM_DISMESSO, idrogeo=_idrogeo(frane_p3p4_pct=18.5))
    assert r.confidenza == "Alta"
    assert r.classificazione == "VINCOLATO"
    assert "VINCOLATO" in r.vincoli and "18.5%" in r.vincoli
    assert any("scala COMUNALE" in c for c in r.caveat)


def test_idraulica_sola_produce_vincolo() -> None:
    r = reconcile_polygon(osm_feature=_OSM_DISMESSO, idrogeo=_idrogeo(idraulica=["p2", "p3"]))
    assert r.classificazione == "VINCOLATO"
    assert "idraulica" in r.vincoli.lower()


def test_discrepanza_tag_dismesso_ma_progetto_attivo_media() -> None:
    # OSM dice dismesso ma ci sono progetti nel comune → discrepanza → Media (non Alta)
    r = reconcile_polygon(
        osm_feature=_OSM_DISMESSO,
        idrogeo=_idrogeo(frane_p3p4_pct=5.0),
        investimenti=[{"clp": "X", "titolo": "Riqualificazione"}],
    )
    assert r.confidenza == "Media"
    assert "disallineamento" in r.discrepanza_osm
    assert "OpenCoesione" in r.stato_attivita


def test_idrogeo_vuoto_non_conta_come_fonte() -> None:
    # RiskIndicators senza superfici esposte → nessun vincolo, resta Bassa
    vuoto = RiskIndicators(cod_comune="1", nome="x", source_url="u", licenza="l")
    r = reconcile_polygon(osm_feature=_OSM_DISMESSO, idrogeo=vuoto)
    assert r.confidenza == "Bassa"
    assert r.vincoli == "da verificare"


def test_greenfield_classificato_libero() -> None:
    r = reconcile_polygon(osm_feature={"osm_type": "way", "osm_id": 7, "kind": "greenfield"})
    assert r.classificazione == "LIBERO"
    assert r.causa_abbandono == "da verificare"  # non è dismesso


def test_causa_abbandono_da_tag() -> None:
    r = reconcile_polygon(osm_feature={"osm_type": "way", "osm_id": 9, "kind": "ruins"})
    assert r.classificazione == "DISMESSO"
    assert "rovina" in r.causa_abbandono


def test_copertura_suolo_risolve_uso_reale_e_alza_confidenza() -> None:
    # tag dismesso + copertura artificiale (impermeabilizzato) → 2 fonti concordi → Alta
    r = reconcile_polygon(osm_feature=_OSM_DISMESSO, land_cover=_lc(macro=1))
    assert r.confidenza == "Alta"
    assert r.uso_reale != "da verificare" and "CLC" in r.uso_reale
    assert not any("Copernicus" in c for c in r.caveat)  # nodo risolto, caveat rimosso
    assert any("Corine Land Cover" in c for c in r.caveat)  # ma resta il caveat di scala


def test_copertura_libero_ma_impermeabilizzato_e_discrepanza() -> None:
    # OSM greenfield (LIBERO) ma copertura artificiale → contraddizione → Media
    r = reconcile_polygon(
        osm_feature={"osm_type": "way", "osm_id": 3, "kind": "greenfield"},
        land_cover=_lc(macro=1),
    )
    assert r.classificazione == "LIBERO"
    assert r.confidenza == "Media"
    assert "impermeabilizzata" in r.discrepanza_osm


def test_dismesso_ma_copertura_non_artificiale_media() -> None:
    r = reconcile_polygon(osm_feature=_OSM_DISMESSO, land_cover=_lc(macro=3))
    assert r.confidenza == "Media"
    assert "rinaturalizzazione" in r.discrepanza_osm


def test_vincolo_paesaggistico_classifica_vincolato_e_alza_confidenza() -> None:
    # tag dismesso + tutela paesaggistica puntuale → 2 fonti → VINCOLATO, Alta
    r = reconcile_polygon(
        osm_feature=_OSM_DISMESSO,
        vincolo_paesaggistico=_paes(vincolato=True, tutele=("Territori costieri",)),
    )
    assert r.classificazione == "VINCOLATO"
    assert r.confidenza == "Alta"
    assert "paesaggistico" in r.vincoli and "Territori costieri" in r.vincoli


def test_vincolo_paesaggistico_interrogato_ma_assente_non_vincola() -> None:
    # PPTR interrogato ma nessuna tutela nel punto → non VINCOLATO, non conta come fonte
    r = reconcile_polygon(osm_feature=_OSM_DISMESSO, vincolo_paesaggistico=_paes(vincolato=False))
    assert r.classificazione == "DISMESSO"
    assert r.confidenza == "Bassa"


def test_vincoli_idrogeo_e_paesaggistico_combinati() -> None:
    r = reconcile_polygon(
        osm_feature=_OSM_DISMESSO,
        idrogeo=_idrogeo(frane_p3p4_pct=10.0),
        vincolo_paesaggistico=_paes(vincolato=True, tutele=("Boschi",)),
    )
    assert r.classificazione == "VINCOLATO"
    assert "idrogeologico" in r.vincoli and "paesaggistico" in r.vincoli


def test_contaminazione_classifica_brownfield_e_alza_confidenza() -> None:
    # SIN al punto + tag dismesso → BROWNFIELD, 2 fonti concordi → Alta
    r = reconcile_polygon(osm_feature=_OSM_DISMESSO, contaminazione=_cont(contaminato=True, sin=True))
    assert r.classificazione == "BROWNFIELD"
    assert r.confidenza == "Alta"
    assert "contaminazione" in r.causa_abbandono
    assert "bonifica" in r.azione_consigliata


def test_contaminazione_sir_comunale_aggiunge_caveat() -> None:
    r = reconcile_polygon(
        osm_feature=_OSM_DISMESSO,
        contaminazione=_cont(contaminato=True, sin=False, sir_cont=5),
    )
    assert r.classificazione == "BROWNFIELD"
    assert any("scala COMUNALE" in c for c in r.caveat)


def test_contaminazione_assente_non_e_brownfield() -> None:
    # procedimenti interrogati ma nessuna contaminazione → resta DISMESSO
    r = reconcile_polygon(
        osm_feature=_OSM_DISMESSO,
        contaminazione=_cont(contaminato=False, sin=False, sir_cont=0),
    )
    assert r.classificazione == "DISMESSO"
    assert r.confidenza == "Bassa"


def test_brownfield_prevale_su_vincolato() -> None:
    # contaminato + anche vincolo idrogeologico → BROWNFIELD (causa più critica),
    # ma il vincolo resta registrato nel campo vincoli
    r = reconcile_polygon(
        osm_feature=_OSM_DISMESSO,
        contaminazione=_cont(contaminato=True, sin=True),
        idrogeo=_idrogeo(frane_p3p4_pct=20.0),
    )
    assert r.classificazione == "BROWNFIELD"
    assert "VINCOLATO" in r.vincoli and "idrogeologico" in r.vincoli


def test_destinazione_pug_risolta_alza_confidenza() -> None:
    # zona PUG "D" (produttiva) + tag dismesso → destinazione risolta, 2 fonti → Alta
    r = reconcile_polygon(osm_feature=_OSM_DISMESSO, destinazione_pug="D")
    assert r.destinazione_pug == "D"
    assert r.confidenza == "Alta"
    assert not any("PUG" in c and "non è ancora" in c for c in r.caveat)  # caveat PUG rimosso


def test_pug_assente_resta_da_verificare() -> None:
    r = reconcile_polygon(osm_feature=_OSM_DISMESSO)
    assert r.destinazione_pug == "da verificare"
    assert any("PUG" in c for c in r.caveat)


def test_frangia_urbana_tag_non_urbano_in_zona_residenziale() -> None:
    # greenfield (OSM: libero) ma zona PUG "C" (espansione residenziale) → FRANGIA §4.3.4
    r = reconcile_polygon(
        osm_feature={"osm_type": "way", "osm_id": 11, "kind": "greenfield"},
        destinazione_pug="C2",
    )
    assert r.classificazione == "FRANGIA"
    assert "frangia" in r.azione_consigliata.lower()


def test_zona_produttiva_non_e_frangia() -> None:
    r = reconcile_polygon(
        osm_feature={"osm_type": "way", "osm_id": 12, "kind": "greenfield"},
        destinazione_pug="D",
    )
    assert r.classificazione == "LIBERO"  # zona D non residenziale → nessuna frangia


def test_id_geometria_e_passthrough() -> None:
    r = reconcile_polygon(osm_feature=_OSM_DISMESSO)
    assert r.id_geometria == "way/42"
    assert r.tag_osm == "brownfield"
    assert r.nome == "Ex fornace" and r.area_mq == 12000
    assert r.url == "https://osm.org/way/42"
