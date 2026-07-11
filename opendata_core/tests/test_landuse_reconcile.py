"""Test del motore di riconciliazione suolo (#127, Parte V Fase 1)."""

from __future__ import annotations

from opendata_core.ispra.models import HazardSlice, RiskIndicators
from opendata_core.landuse import SoilRecord, reconcile_polygon

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


def test_id_geometria_e_passthrough() -> None:
    r = reconcile_polygon(osm_feature=_OSM_DISMESSO)
    assert r.id_geometria == "way/42"
    assert r.tag_osm == "brownfield"
    assert r.nome == "Ex fornace" and r.area_mq == 12000
    assert r.url == "https://osm.org/way/42"
