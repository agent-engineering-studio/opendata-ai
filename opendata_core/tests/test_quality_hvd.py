"""Test della stima HVD a livello di singolo file (Data Quality Lab / #102)."""

from __future__ import annotations

from opendata_core.quality import advise_hvd, profile_csv, profile_geojson

_GJ = (
    '{"type":"FeatureCollection","features":'
    '[{"type":"Feature","geometry":{"type":"Point","coordinates":[16.87,41.12]},"properties":{}}]}'
)


def test_mobilita_da_colonne_multiple() -> None:
    csv = "linea;fermate;orari;passeggeri\n1;Piazza Moro;07:30;120\n"
    r = advise_hvd(profile_csv(csv))
    top = r["categorie"][0]
    assert top["codice"] == "mobility"
    assert top["etichetta"] == "Mobilità"
    assert top["confidenza"] == "media"  # 2 indizi: fermate, orari
    assert top["tema_eu"] == "TRAN"
    assert any("fermate" in i for i in top["indizi"])
    assert "verdetto" in r["nota"]


def test_confidenza_alta_con_tre_indizi() -> None:
    csv = "gtfs_id;fermate;orari\n1;x;y\n"
    r = advise_hvd(profile_csv(csv))
    assert r["categorie"][0]["codice"] == "mobility"
    assert r["categorie"][0]["confidenza"] == "alta"


def test_singolo_indizio_resta_bassa() -> None:
    csv = "id;temperatura\n1;20\n"
    r = advise_hvd(profile_csv(csv))
    meteo = next(c for c in r["categorie"] if c["codice"] == "meteorological")
    assert meteo["confidenza"] == "bassa"


def test_geojson_geospaziale_alta() -> None:
    r = advise_hvd(profile_geojson(_GJ))
    top = r["categorie"][0]
    assert top["codice"] == "geospatial"
    assert top["confidenza"] == "alta"
    assert any("GeoJSON" in i for i in top["indizi"])


def test_coordinate_indizio_geospaziale() -> None:
    csv = "nome;lat;lon\nBari;41.1;16.9\n"
    r = advise_hvd(profile_csv(csv))
    geo = next(c for c in r["categorie"] if c["codice"] == "geospatial")
    assert any("coordinate" in i for i in geo["indizi"])
    assert geo["confidenza"] == "bassa"  # un solo indizio strutturale


def test_titolo_e_nome_file_contano() -> None:
    csv = "a;b\n1;2\n"  # colonne mute
    r = advise_hvd(
        profile_csv(csv),
        titolo="Qualità dell'aria — centraline",
        url="https://dati.example.it/download/emissioni-pm10.csv?anno=2024",
    )
    amb = next(c for c in r["categorie"] if c["codice"] == "earth_observation_environment")
    assert amb["confidenza"] == "media"  # "qualità dell'aria" (titolo) + "emission" (nome file)


def test_underscore_nei_nomi_colonna() -> None:
    # "piste_ciclabili" deve combaciare con la keyword multi-parola
    csv = "piste_ciclabili;km\nA;3\n"
    r = advise_hvd(profile_csv(csv))
    assert r["categorie"][0]["codice"] == "mobility"


def test_nessuna_evidenza_lista_vuota_e_nota_onesta() -> None:
    csv = "a;b;c\n1;2;3\n"
    r = advise_hvd(profile_csv(csv))
    assert r["categorie"] == []
    assert "euristica" in r["nota"]


def test_categorie_multiple_ordinate_per_evidenza() -> None:
    csv = "fermate;orari;temperatura\n1;2;3\n"
    r = advise_hvd(profile_csv(csv))
    codici = [c["codice"] for c in r["categorie"]]
    assert codici[0] == "mobility"  # 2 indizi > 1 di meteo
    assert "meteorological" in codici
