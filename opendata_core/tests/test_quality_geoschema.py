"""Test dello schema geografico PostGIS/GeoPackage da GeoJSON (Data Quality Lab #51)."""

from __future__ import annotations

from opendata_core.quality import infer_geo_schema

_GJ_PUNTI = (
    '{"type":"FeatureCollection","features":['
    '{"type":"Feature","geometry":{"type":"Point","coordinates":[11.37,44.49]},'
    '"properties":{"nome":"Bari","popolazione":320475,"attivo":true}},'
    '{"type":"Feature","geometry":{"type":"Point","coordinates":[16.86,41.11]},'
    '"properties":{"nome":"Modugno","popolazione":37800,"attivo":false}}'
    ']}'
)


def test_ddl_postgis_con_geometria_e_proprieta() -> None:
    r = infer_geo_schema(_GJ_PUNTI, table_name="comuni")
    assert r["tabella"] == "comuni"
    assert r["geometria"] == "Point"
    assert "CREATE TABLE comuni" in r["ddl_postgis"]
    assert "geom GEOMETRY(Point, 4326)" in r["ddl_postgis"]
    assert "CREATE INDEX idx_comuni_geom ON comuni USING GIST (geom)" in r["ddl_postgis"]
    tipi = {c["original"]: c["sql_type"] for c in r["colonne"]}
    assert tipi["nome"] == "TEXT"
    assert tipi["popolazione"] == "BIGINT"
    assert tipi["attivo"] == "BOOLEAN"


def test_comando_geopackage_presente() -> None:
    r = infer_geo_schema(_GJ_PUNTI)
    assert r["comando_geopackage"] == "ogr2ogr -f GPKG dataset.gpkg input.geojson"


def test_geometrie_miste_usa_tipo_generico() -> None:
    gj = (
        '{"type":"FeatureCollection","features":['
        '{"type":"Feature","geometry":{"type":"Point","coordinates":[1,1]},"properties":{}},'
        '{"type":"Feature","geometry":{"type":"LineString","coordinates":[[1,1],[2,2]]},"properties":{}}'
        ']}'
    )
    r = infer_geo_schema(gj)
    assert "geom GEOMETRY(GEOMETRY, 4326)" in r["ddl_postgis"]
    assert any("miste" in n for n in r["note"])


def test_nessuna_feature() -> None:
    r = infer_geo_schema('{"type":"FeatureCollection","features":[]}')
    assert r["ddl_postgis"] is None
    assert r["note"]


def test_json_non_valido() -> None:
    r = infer_geo_schema("non è json")
    assert r["ddl_postgis"] is None
    assert "JSON" in r["note"][0]
