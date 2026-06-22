"""Test del convertitore tabella → GeoJSON (Data Quality Lab / Punto 03 #51)."""

from __future__ import annotations

from opendata_core.quality import csv_to_geojson, json_to_geojson


def test_csv_autodetect_latlon_e_properties() -> None:
    csv = "nome;lat;lon;abitanti\nBari;41,12;16,87;320000\nGioia del Colle;40,80;16,92;27000\n"
    r = csv_to_geojson(csv)

    assert r["ok"] is True
    assert r["lat_field"] == "lat" and r["lon_field"] == "lon"
    assert r["n_features"] == 2
    f0 = r["geojson"]["features"][0]
    # GeoJSON vuole [lon, lat], e la virgola decimale IT è normalizzata
    assert f0["geometry"]["coordinates"] == [16.87, 41.12]
    # le altre colonne diventano properties, le coordinate no
    assert f0["properties"] == {"nome": "Bari", "abitanti": "320000"}
    assert "lat" not in f0["properties"]


def test_csv_senza_coordinate_segnala_candidate() -> None:
    r = csv_to_geojson("comune,popolazione\nBari,320000\n")
    assert r["ok"] is False
    assert "coordinate" in r["error"].lower()
    assert r["candidate_columns"] == ["comune", "popolazione"]


def test_csv_salta_righe_invalide_e_fuori_range() -> None:
    csv = (
        "id,latitude,longitude\n"
        "1,41.1,16.8\n"        # ok
        "2,,16.8\n"            # lat mancante → saltata
        "3,612345,4912345\n"  # coordinate proiettate (fuori range WGS84) → saltata
    )
    r = csv_to_geojson(csv)
    assert r["n_features"] == 1
    assert r["n_skipped"] == 2
    assert any("proiettate" in w for w in r["warnings"])


def test_json_array_di_record() -> None:
    js = '[{"nome":"Bari","y":41.1,"x":16.8},{"nome":"Monopoli","y":40.9,"x":17.3}]'
    r = json_to_geojson(js)
    assert r["ok"] is True
    assert r["lat_field"] == "y" and r["lon_field"] == "x"
    assert r["n_features"] == 2
    assert r["geojson"]["features"][0]["geometry"]["coordinates"] == [16.8, 41.1]


def test_json_geojson_passthrough() -> None:
    gj = '{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Point","coordinates":[1,2]},"properties":{}}]}'
    r = json_to_geojson(gj)
    assert r["ok"] is True
    assert r["n_features"] == 1
    assert any("già un GeoJSON" in w for w in r["warnings"])


def test_override_colonne_coordinate() -> None:
    # colonne con nomi non standard → override esplicito
    csv = "citta;coord_nord;coord_est\nBari;41.1;16.8\n"
    r = csv_to_geojson(csv, lat_field="coord_nord", lon_field="coord_est")
    assert r["ok"] is True
    assert r["n_features"] == 1
