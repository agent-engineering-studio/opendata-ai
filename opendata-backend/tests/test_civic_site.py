"""Test del generatore sito civico (Fase 4, I1): snapshot fixture → HTML valido + zip."""

from __future__ import annotations

import io
import zipfile

from opendata_backend.civic.site import bundle_zip, generate_site

_SNAPSHOT = {
    "istat_code": "072021",
    "snapshot_id": "2026-H1",
    "created_at": "2026-06-30T00:00:00+00:00",
    "sources_version": "2026-06",
    "kpi_version": "1",
    "payload": {
        "name": "Gioia del Colle",
        "population": 27889,
        "center": {"lat": 40.7986, "lon": 16.9268},
        "investimenti": {"n_progetti": 2, "finanziamento_totale": 350000.0,
                         "per_tema": [{"tema": "Trasporti", "finanziamento": 250000.0}]},
        "projects": [{"titolo": "Scuola", "tema": "Istruzione", "stato": "concluso"}],
        "report": {"sezioni": {"idee_sviluppo": [{"category": "Bar", "score": 88.8, "rationale": "ok"}],
                               "gap_dato": ["Dati occupazione non integrati."]}},
        "stato_suolo": [{
            "id_geometria": "way/1", "nome": "Ex fornace", "tag_osm": "brownfield",
            "uso_reale": "Superfici artificiali (CLC 111)", "destinazione_pug": "D",
            "catasto": "da verificare", "proprieta": "da verificare",
            "stato_attivita": "inattivo/dismesso", "vincoli": "da verificare",
            "classificazione": "BROWNFIELD", "discrepanza_osm": "n/d",
            "causa_abbandono": "contaminazione accertata", "azione_consigliata": "bonifica necessaria",
            "confidenza": "Alta", "caveat": [], "url": "https://osm.org/way/1", "area_mq": 5000,
        }],
    },
    "kpi": {"accessibilita_servizi": {"label": "Accessibilità", "value": 50.0, "unit": "/100",
                                      "direction": "up", "source": "feature_store", "definition": "..."}},
}

_DIFF = {
    "summary": {"opere_concluse": 1, "opere_nuove": 1, "kpi_migliorati": 1, "kpi_peggiorati": 0},
    "opere": {"fatte": [{"clp": "1", "titolo": "Scuola"}], "nuove": [], "in_corso": []},
    "kpi": [{"label": "Accessibilità", "da": 40, "a": 50, "esito": "migliorato"}],
}
_MATURITY = {"level": "Fast-tracker", "overall": 67.0,
             "dimensions": {"policy": 66.7, "portal": 75.0, "quality": 72.7, "impact": 48.7}}


def test_generate_site_pages() -> None:
    files = generate_site(_SNAPSHOT, diff=_DIFF, maturity=_MATURITY)
    for page in ("index.html", "investimenti.html", "opportunita.html", "suolo.html", "rischi.html",
                 "avanzamento.html", "community.html", "scorecard.html", "mappa.html", "style.css"):
        assert page in files
    idx = files["index.html"]
    assert idx.startswith("<!DOCTYPE html>") and idx.rstrip().endswith("</html>")
    assert "Gioia del Colle" in idx
    assert "2026-H1" in idx and "2026-06" in idx  # riproducibilità nel footer
    assert "Accessibilità" in idx


def test_site_traceability_and_content() -> None:
    files = generate_site(_SNAPSHOT, diff=_DIFF, maturity=_MATURITY)
    assert "opencoesione.gov.it" in files["investimenti.html"]  # fonte+licenza
    assert "350000" in files["investimenti.html"]
    assert "Bar" in files["opportunita.html"]
    assert "occupazione" in files["rischi.html"]
    assert "opere concluse" in files["avanzamento.html"]
    assert "Fast-tracker" in files["scorecard.html"]
    assert "leaflet" in files["mappa.html"].lower()  # mappa Leaflet CDN


def test_bundle_zip() -> None:
    files = generate_site(_SNAPSHOT)
    data = bundle_zip(files)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = set(zf.namelist())
        assert "index.html" in names and "style.css" in names
        assert zf.read("index.html").decode("utf-8").startswith("<!DOCTYPE html>")


def test_suolo_page_content() -> None:
    """#130 4c: la pagina 'Stato del suolo' mostra il record §4.5 con classificazione,
    badge di confidenza, disclaimer-modello e proprietà mai presunta pubblica."""
    files = generate_site(_SNAPSHOT, diff=_DIFF, maturity=_MATURITY)
    html = files["suolo.html"]
    assert "Stato reale del suolo" in html
    assert "Ex fornace" in html and "Brownfield" in html
    assert "Confidenza alta" in html
    assert "mai presunta pubblica" in html
    # nav include la pagina
    assert 'href="suolo.html"' in files["index.html"]


def test_suolo_page_vuota_senza_record() -> None:
    snap = {**_SNAPSHOT, "payload": {**_SNAPSHOT["payload"], "stato_suolo": []}}
    files = generate_site(snap)
    assert "Nessuna area candidata riconciliata" in files["suolo.html"]
