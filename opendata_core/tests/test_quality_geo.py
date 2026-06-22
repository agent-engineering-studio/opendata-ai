"""Test del geo doctor — diagnosi GeoJSON (Data Quality Lab #49)."""

from __future__ import annotations

import json

from opendata_core.quality import profile_geojson


def _codes(rep: dict) -> set[str]:
    return {f["codice"] for f in rep["findings"]}


def _fc(features: list[dict], crs: dict | None = None) -> str:
    obj: dict = {"type": "FeatureCollection", "features": features}
    if crs:
        obj["crs"] = crs
    return json.dumps(obj)


def _feat(geom: dict | None) -> dict:
    return {"type": "Feature", "geometry": geom, "properties": {}}


def test_wgs84_pulito() -> None:
    rep = profile_geojson(_fc([
        _feat({"type": "Point", "coordinates": [11.37, 44.49]}),
        _feat({"type": "Point", "coordinates": [16.92, 40.80]}),
    ]))
    assert rep["format"] == "GEOJSON"
    assert rep["features"] == 2
    assert rep["crs_wgs84"] is True
    assert rep["geometrie"] == {"Point": 2}
    assert rep["punteggio"] >= 90
    assert rep["bbox"] == [11.37, 40.8, 16.92, 44.49]


def test_coordinate_proiettate() -> None:
    # UTM 32N (metri): x~600k, y~4.9M → non lon/lat
    rep = profile_geojson(_fc([
        _feat({"type": "Point", "coordinates": [612345.0, 4912345.0]}),
    ]))
    assert rep["crs_wgs84"] is False
    assert "coord_proiettate" in _codes(rep)


def test_crs_dichiarato_non_wgs84() -> None:
    rep = profile_geojson(_fc(
        [_feat({"type": "Point", "coordinates": [612345.0, 4912345.0]})],
        crs={"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::32632"}},
    ))
    assert rep["crs"] == "EPSG:32632"
    assert rep["crs_wgs84"] is False
    assert "crs_non_wgs84" in _codes(rep)


def test_topojson_segnalato() -> None:
    rep = profile_geojson(json.dumps({"type": "Topology", "objects": {}}))
    assert rep["punteggio"] == 0
    assert "topojson" in _codes(rep)


def test_json_non_valido() -> None:
    rep = profile_geojson("{non valido")
    assert rep["punteggio"] == 0
    assert "json_non_valido" in _codes(rep)


def test_feature_collection_vuota() -> None:
    rep = profile_geojson(_fc([]))
    assert "nessuna_feature" in _codes(rep)


def test_geometrie_vuote() -> None:
    rep = profile_geojson(_fc([
        _feat({"type": "Point", "coordinates": [11.0, 44.0]}),
        _feat(None),
        _feat({"type": "Polygon", "coordinates": []}),
    ]))
    assert "geometrie_vuote" in _codes(rep)


def test_geometria_nuda() -> None:
    rep = profile_geojson(json.dumps({"type": "LineString", "coordinates": [[11.0, 44.0], [11.1, 44.1]]}))
    assert rep["features"] == 1
    assert rep["geometrie"] == {"LineString": 1}
    assert rep["crs_wgs84"] is True
