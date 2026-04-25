"""Smoke tests for the CKAN HTTP client using pytest-httpx.

Coverage spans all 13 dati.gov.it thematic groups:
  agricoltura, economia, cultura, energia, ambiente, governo,
  salute, internazionali, giustizia, regioni, societa, scienza, trasporti

For each theme at least 5 mock tests verify package_search / package_show
against real dataset IDs and resource formats found on the portal.

Resource-format rule applied in assertions:
  • CSV, JSON, GeoJSON, TXT → "downloadable" (agent should download & read)
  • everything else (PDF, XLSX, XLS, SHP, KML, WMS, …) → "url-only"
"""

from __future__ import annotations

import pytest

from ckan_mcp.ckan_client import CkanClient, CkanError, _normalize_base

# ─── Constants ────────────────────────────────────────────────────────────────

DATI_GOV_BASE = "https://www.dati.gov.it/opendata"
POPOLAZIONE_DATASET_ID = "2908fe96-58c4-40fe-8b29-9d4d78715ba7"

DOWNLOADABLE_FORMATS = {"CSV", "JSON", "GeoJSON", "GEOJSON", "TXT"}


def _classify_resources(resources: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split resources into downloadable (read content) vs url-only."""
    downloadable = [r for r in resources if r["format"].upper() in {f.upper() for f in DOWNLOADABLE_FORMATS}]
    url_only = [r for r in resources if r["format"].upper() not in {f.upper() for f in DOWNLOADABLE_FORMATS}]
    return downloadable, url_only


def test_normalize_base_default():
    """Default base URL should be the dati.gov.it /opendata CKAN instance."""
    url = _normalize_base(None)
    assert url == DATI_GOV_BASE + "/"


def test_normalize_base_strips_trailing_slash():
    url = _normalize_base("https://data.gov.uk/")
    assert url == "https://data.gov.uk/"


def test_normalize_base_adds_scheme():
    url = _normalize_base("data.gov.uk")
    assert url == "https://data.gov.uk/"


# ─── Action helpers ──────────────────────────────────────────────────────────


async def test_action_success(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://example.org/api/3/action/status_show",
        json={"success": True, "result": {"site_title": "Example", "ckan_version": "2.10"}},
    )
    async with CkanClient() as c:
        result = await c.action("status_show", base_url="https://example.org")
    assert result["site_title"] == "Example"


async def test_action_failure_raises(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://example.org/api/3/action/package_show?id=missing",
        json={"success": False, "error": {"message": "Not found"}},
    )
    async with CkanClient() as c:
        with pytest.raises(CkanError):
            await c.action("package_show", base_url="https://example.org", params={"id": "missing"})


# ─── download_resource tests ────────────────────────────────────────────────


async def test_download_resource_csv(httpx_mock):
    """download_resource returns text content for a CSV file."""
    csv_url = "https://data.example.org/dataset.csv"
    csv_body = "nome,eta\nMario,30\nLuigi,25\n"
    httpx_mock.add_response(
        method="GET",
        url=csv_url,
        text=csv_body,
        headers={"content-type": "text/csv; charset=utf-8"},
    )
    async with CkanClient() as c:
        result = await c.download_resource(csv_url)
    assert result["url"] == csv_url
    assert result["content"] == csv_body
    assert result["truncated"] is False
    assert result["size_bytes"] == len(csv_body.encode())
    assert "csv" in result["content_type"]


async def test_download_resource_json(httpx_mock):
    """download_resource returns text content for a JSON file."""
    json_url = "https://data.example.org/dataset.json"
    json_body = '{"records": [{"id": 1, "name": "test"}]}'
    httpx_mock.add_response(
        method="GET",
        url=json_url,
        text=json_body,
        headers={"content-type": "application/json"},
    )
    async with CkanClient() as c:
        result = await c.download_resource(json_url)
    assert result["content"] == json_body
    assert result["truncated"] is False


async def test_download_resource_truncates_large_file(httpx_mock):
    """download_resource truncates content exceeding max_bytes."""
    csv_url = "https://data.example.org/big.csv"
    big_body = "x" * 2000
    httpx_mock.add_response(method="GET", url=csv_url, text=big_body)
    async with CkanClient() as c:
        result = await c.download_resource(csv_url, max_bytes=500)
    assert result["truncated"] is True
    assert len(result["content"]) == 500
    assert result["size_bytes"] == 2000


async def test_download_resource_http_error(httpx_mock):
    """download_resource raises CkanError on HTTP 404."""
    bad_url = "https://data.example.org/missing.csv"
    httpx_mock.add_response(method="GET", url=bad_url, status_code=404)
    async with CkanClient() as c:
        with pytest.raises(CkanError, match="Failed to download"):
            await c.download_resource(bad_url)


async def test_download_resource_geojson(httpx_mock):
    """download_resource works for GeoJSON files."""
    geojson_url = "https://data.example.org/places.geojson"
    geojson_body = '{"type":"FeatureCollection","features":[]}'
    httpx_mock.add_response(
        method="GET",
        url=geojson_url,
        text=geojson_body,
        headers={"content-type": "application/geo+json"},
    )
    async with CkanClient() as c:
        result = await c.download_resource(geojson_url)
    assert result["content"] == geojson_body
    assert result["truncated"] is False


# ─── dati.gov.it package_show mock ──────────────────────────────────────────


async def test_package_show_popolazione(httpx_mock):
    """Simulates package_show for 'Popolazione residente per quartiere e per classe di età'."""
    httpx_mock.add_response(
        method="GET",
        url=(
            f"{DATI_GOV_BASE}/api/3/action/package_show"
            f"?id={POPOLAZIONE_DATASET_ID}"
        ),
        json={
            "success": True,
            "result": {
                "id": POPOLAZIONE_DATASET_ID,
                "title": "Popolazione residente per quartiere e per classe di età al 31/12/2025",
                "organization": {"title": "Comune di Firenze"},
                "resources": [
                    {"id": "d5cdaf9a-33c2-4ba9-a971-e3eff0fcb238", "format": "PDF"},
                    {"id": "c34c4427-a56e-4c29-b5fb-47529e973820", "format": "CSV"},
                    {"id": "d0991309-6033-4880-953d-eae1c4027cbb", "format": "XLSX"},
                ],
            },
        },
    )
    async with CkanClient() as c:
        result = await c.action(
            "package_show",
            base_url=DATI_GOV_BASE,
            params={"id": POPOLAZIONE_DATASET_ID},
        )
    assert result["title"].startswith("Popolazione residente")
    assert len(result["resources"]) == 3
    formats = [r["format"] for r in result["resources"]]
    assert "CSV" in formats


async def test_package_search_popolazione(httpx_mock):
    """Simulates a search for 'popolazione quartiere' on dati.gov.it."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=popolazione+quartiere&rows=5&start=0",
        json={
            "success": True,
            "result": {
                "count": 1,
                "results": [
                    {
                        "id": POPOLAZIONE_DATASET_ID,
                        "title": "Popolazione residente per quartiere e per classe di età al 31/12/2025",
                    }
                ],
            },
        },
    )
    async with CkanClient() as c:
        result = await c.action(
            "package_search",
            base_url=DATI_GOV_BASE,
            params={"q": "popolazione quartiere", "rows": 5, "start": 0},
        )
    assert result["count"] >= 1
    assert POPOLAZIONE_DATASET_ID in [r["id"] for r in result["results"]]


# ══════════════════════════════════════════════════════════════════════════════
#  THEME 1 — AGRICOLTURA  (575 datasets on dati.gov.it)
# ══════════════════════════════════════════════════════════════════════════════


async def test_agr_search_fattorie_didattiche(httpx_mock):
    """AGR-1: search for fattorie didattiche."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=fattorie+didattiche&rows=5&start=0",
        json={"success": True, "result": {"count": 12, "results": [
            {"id": "fd-001", "title": "Fattorie didattiche"},
        ]}},
    )
    async with CkanClient() as c:
        result = await c.action("package_search", base_url=DATI_GOV_BASE,
                                params={"q": "fattorie didattiche", "rows": 5, "start": 0})
    assert result["count"] >= 1


async def test_agr_show_fattorie_didattiche(httpx_mock):
    """AGR-2: package_show fattorie didattiche – CSV + XLSX resources."""
    ds_id = "fd-001"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Fattorie didattiche",
            "resources": [
                {"id": "r1", "format": "CSV", "url": "https://example.org/fattorie.csv"},
                {"id": "r2", "format": "XLSX", "url": "https://example.org/fattorie.xlsx"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1 and dl[0]["format"] == "CSV"
    assert len(uo) == 1 and uo[0]["format"] == "XLSX"


async def test_agr_search_biologica(httpx_mock):
    """AGR-3: search agricoltura biologica."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=agricoltura+biologica&rows=5&start=0",
        json={"success": True, "result": {"count": 5, "results": [
            {"id": "ab-001", "title": "Agricoltura Biologica"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "agricoltura biologica", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_agr_show_aziende_agricole(httpx_mock):
    """AGR-4: package_show aziende agricole – CSV, XML, ODS, XSD."""
    ds_id = "az-agr-001"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Aziende agricole",
            "resources": [
                {"id": "r1", "format": "CSV", "url": "https://example.org/aziende.csv"},
                {"id": "r2", "format": "XSD", "url": "https://example.org/aziende.xsd"},
                {"id": "r3", "format": "ODS", "url": "https://example.org/aziende.ods"},
                {"id": "r4", "format": "XML", "url": "https://example.org/aziende.xml"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1  # only CSV
    assert len(uo) == 3  # XSD, ODS, XML


async def test_agr_search_pesca_porti(httpx_mock):
    """AGR-5: search pesca porti pugliesi."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=pesca+porti+pugliesi&rows=5&start=0",
        json={"success": True, "result": {"count": 3, "results": [
            {"id": "pp-001", "title": "Appesca porti pugliesi"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "pesca porti pugliesi", "rows": 5, "start": 0})
    assert r["count"] >= 1


# ══════════════════════════════════════════════════════════════════════════════
#  THEME 2 — ECONOMIA E FINANZE  (6759 datasets)
# ══════════════════════════════════════════════════════════════════════════════


async def test_eco_search_edicole(httpx_mock):
    """ECO-1: search edicole – GeoJSON + SHP + WMS."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=edicole&rows=5&start=0",
        json={"success": True, "result": {"count": 4, "results": [
            {"id": "ed-001", "title": "Edicole"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "edicole", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_eco_show_edicole_formats(httpx_mock):
    """ECO-2: edicole – GeoJSON downloadable, SHP+WMS url-only."""
    ds_id = "ed-001"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Edicole",
            "resources": [
                {"id": "r1", "format": "GeoJSON", "url": "https://example.org/edicole.geojson"},
                {"id": "r2", "format": "SHP", "url": "https://example.org/edicole.shp"},
                {"id": "r3", "format": "WMS", "url": "https://example.org/edicole/wms"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1 and dl[0]["format"] == "GeoJSON"
    assert len(uo) == 2


async def test_eco_search_lavoro_cessazioni(httpx_mock):
    """ECO-3: search lavoro cessazioni – CSV."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=lavoro+cessazioni&rows=5&start=0",
        json={"success": True, "result": {"count": 8, "results": [
            {"id": "lc-001", "title": "Lavoro cessazioni"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "lavoro cessazioni", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_eco_search_lavoro_avviamenti(httpx_mock):
    """ECO-4: search lavoro avviamenti."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=lavoro+avviamenti&rows=5&start=0",
        json={"success": True, "result": {"count": 6, "results": [
            {"id": "la-001", "title": "Lavoro avviamenti"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "lavoro avviamenti", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_eco_search_collocamento_mirato(httpx_mock):
    """ECO-5: search collocamento mirato – CSV."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=collocamento+mirato&rows=5&start=0",
        json={"success": True, "result": {"count": 2, "results": [
            {"id": "cm-001", "title": "Lavoro collocamento mirato"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "collocamento mirato", "rows": 5, "start": 0})
    assert r["count"] >= 1


# ══════════════════════════════════════════════════════════════════════════════
#  THEME 3 — ISTRUZIONE, CULTURA E SPORT  (4142 datasets)
# ══════════════════════════════════════════════════════════════════════════════


async def test_cul_search_anagrafe_scuole(httpx_mock):
    """CUL-1: anagrafe strutture edilizie scuole."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=anagrafe+strutture+scuole&rows=5&start=0",
        json={"success": True, "result": {"count": 3, "results": [
            {"id": "as-001", "title": "Anagrafe strutture edilizie scuole"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "anagrafe strutture scuole", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_cul_show_anagrafe_scuole(httpx_mock):
    """CUL-2: anagrafe scuole – CSV downloadable, PDF+ZIP url-only."""
    ds_id = "as-001"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Anagrafe strutture edilizie scuole",
            "resources": [
                {"id": "r1", "format": "CSV", "url": "https://example.org/scuole.csv"},
                {"id": "r2", "format": "PDF", "url": "https://example.org/scuole.pdf"},
                {"id": "r3", "format": "ZIP", "url": "https://example.org/scuole.zip"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1 and dl[0]["format"] == "CSV"
    assert len(uo) == 2


async def test_cul_search_popolazione_scolastica(httpx_mock):
    """CUL-3: search popolazione scolastica."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=popolazione+scolastica&rows=5&start=0",
        json={"success": True, "result": {"count": 5, "results": [
            {"id": "ps-001", "title": "Popolazione scolastica"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "popolazione scolastica", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_cul_search_pendolarismo_scolastico(httpx_mock):
    """CUL-4: search pendolarismo scolastico."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=pendolarismo+scolastico&rows=5&start=0",
        json={"success": True, "result": {"count": 2, "results": [
            {"id": "pend-001", "title": "Pendolarismo scolastico"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "pendolarismo scolastico", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_cul_search_alunni_classi(httpx_mock):
    """CUL-5: search alunni classi scuole."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=alunni+classi+scuole&rows=5&start=0",
        json={"success": True, "result": {"count": 4, "results": [
            {"id": "ac-001", "title": "Alunni classi scuole"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "alunni classi scuole", "rows": 5, "start": 0})
    assert r["count"] >= 1


# ══════════════════════════════════════════════════════════════════════════════
#  THEME 4 — ENERGIA  (376 datasets)
# ══════════════════════════════════════════════════════════════════════════════


async def test_ene_search_ricarica_auto_elettriche(httpx_mock):
    """ENE-1: search stazioni ricarica auto elettriche."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=stazioni+ricarica+auto+elettriche&rows=5&start=0",
        json={"success": True, "result": {"count": 3, "results": [
            {"id": "sr-001", "title": "Stazioni ricarica auto elettriche"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "stazioni ricarica auto elettriche", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_ene_search_punti_luce(httpx_mock):
    """ENE-2: search punti luce illuminazione."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=punti+luce+illuminazione&rows=5&start=0",
        json={"success": True, "result": {"count": 2, "results": [
            {"id": "pl-001", "title": "Punti luce"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "punti luce illuminazione", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_ene_search_comunita_energetiche(httpx_mock):
    """ENE-3: search comunità energetiche rinnovabili."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=comunita+energetiche+rinnovabili&rows=5&start=0",
        json={"success": True, "result": {"count": 1, "results": [
            {"id": "cer-001", "title": "Comunità Energetiche Rinnovabili"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "comunita energetiche rinnovabili", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_ene_show_fotovoltaici(httpx_mock):
    """ENE-4: produzione fotovoltaici – CSV + JSON downloadable."""
    ds_id = "fv-001"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Produzione fotovoltaici",
            "resources": [
                {"id": "r1", "format": "CSV", "url": "https://example.org/fotov.csv"},
                {"id": "r2", "format": "JSON", "url": "https://example.org/fotov.json"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 2  # both CSV and JSON are downloadable
    assert len(uo) == 0


async def test_ene_show_consumi_serie_storica(httpx_mock):
    """ENE-5: consumi energia serie storica – JSON+CSV download, XLS url-only."""
    ds_id = "ces-001"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Consumi energia elettrica serie storica",
            "resources": [
                {"id": "r1", "format": "JSON", "url": "https://example.org/consumi.json"},
                {"id": "r2", "format": "CSV", "url": "https://example.org/consumi.csv"},
                {"id": "r3", "format": "XLS", "url": "https://example.org/consumi.xls"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 2  # JSON + CSV
    assert len(uo) == 1  # XLS


# ══════════════════════════════════════════════════════════════════════════════
#  THEME 5 — AMBIENTE  (8832 datasets)
# ══════════════════════════════════════════════════════════════════════════════


async def test_amb_search_aree_verdi(httpx_mock):
    """AMB-1: search aree verdi."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=aree+verdi&rows=5&start=0",
        json={"success": True, "result": {"count": 15, "results": [
            {"id": "av-001", "title": "Aree verdi"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "aree verdi", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_amb_show_aree_verdi_formats(httpx_mock):
    """AMB-2: aree verdi – WMS, KML, SHP url-only; no downloadable."""
    ds_id = "av-001"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Aree verdi",
            "resources": [
                {"id": "r1", "format": "WMS", "url": "https://example.org/aree_verdi/wms"},
                {"id": "r2", "format": "KML", "url": "https://example.org/aree_verdi.kml"},
                {"id": "r3", "format": "SHP", "url": "https://example.org/aree_verdi.shp"},
                {"id": "r4", "format": "RDF", "url": "https://example.org/aree_verdi.rdf"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 0
    assert len(uo) == 4


async def test_amb_show_distributori_geojson(httpx_mock):
    """AMB-3: distributori carburante – GeoJSON downloadable."""
    ds_id = "dc-001"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Distributori di carburante",
            "resources": [
                {"id": "r1", "format": "SHP", "url": "https://example.org/distrib.shp"},
                {"id": "r2", "format": "WMS", "url": "https://example.org/distrib/wms"},
                {"id": "r3", "format": "GeoJSON", "url": "https://example.org/distrib.geojson"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1 and dl[0]["format"] == "GeoJSON"
    assert len(uo) == 2


async def test_amb_search_alberi_frutto(httpx_mock):
    """AMB-4: search alberi da frutto."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=alberi+frutto&rows=5&start=0",
        json={"success": True, "result": {"count": 2, "results": [
            {"id": "af-001", "title": "Alberi da frutto"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "alberi frutto", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_amb_search_faglie_attive(httpx_mock):
    """AMB-5: search faglie attive."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=faglie+attive&rows=5&start=0",
        json={"success": True, "result": {"count": 1, "results": [
            {"id": "fa-001", "title": "Faglie attive"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "faglie attive", "rows": 5, "start": 0})
    assert r["count"] >= 1


# ══════════════════════════════════════════════════════════════════════════════
#  THEME 6 — GOVERNO E SETTORE PUBBLICO  (35219 datasets)
# ══════════════════════════════════════════════════════════════════════════════


async def test_gov_show_area_stradale(httpx_mock):
    """GOV-1: area stradale Vinci – real ID, GeoJSON downloadable."""
    ds_id = "8ad84dc3-da4e-4146-9ed6-ae5b7858bec4"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Area stradale",
            "organization": {"title": "Regione Toscana"},
            "resources": [
                {"id": "r1", "format": "ZIP", "url": "https://vinci.ldpgis.it/area_stradale.zip"},
                {"id": "r2", "format": "GeoJSON", "url": "https://vinci.ldpgis.it/area_stradale.geojson"},
                {"id": "r3", "format": "KML", "url": "https://vinci.ldpgis.it/area_stradale.kml"},
                {"id": "r4", "format": "SHP", "url": "https://vinci.ldpgis.it/area_stradale.shp"},
                {"id": "r5", "format": "WFS", "url": "https://vinci.ldpgis.it/wfs"},
                {"id": "r6", "format": "WMS", "url": "https://vinci.ldpgis.it/wms"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1  # GeoJSON
    assert len(uo) == 5  # ZIP, KML, SHP, WFS, WMS


async def test_gov_show_norme_tecniche(httpx_mock):
    """GOV-2: Norme Tecniche di Attuazione – TXT, CSV, JSON downloadable; PDF url-only."""
    ds_id = "da3db55b-b3f4-44fb-b4de-f1e5cf35c8fb"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Norme Tecniche di Attuazione",
            "resources": [
                {"id": "r1", "format": "TXT", "url": "https://barga.ldpgis.it/norme.txt"},
                {"id": "r2", "format": "CSV", "url": "https://barga.ldpgis.it/norme.csv"},
                {"id": "r3", "format": "JSON", "url": "https://barga.ldpgis.it/norme.json"},
                {"id": "r4", "format": "PDF", "url": "https://barga.ldpgis.it/norme.pdf"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 3  # TXT, CSV, JSON
    assert len(uo) == 1  # PDF


async def test_gov_search_consumo_suolo(httpx_mock):
    """GOV-3: search consumo del suolo."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=consumo+suolo&rows=5&start=0",
        json={"success": True, "result": {"count": 10, "results": [
            {"id": "e83822c0-434d-4284-9ff5-538f737a705a", "title": "Consumo del suolo"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "consumo suolo", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_gov_search_destinazione_uso(httpx_mock):
    """GOV-4: search destinazione d'uso catastale."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=destinazione+uso+catastale&rows=5&start=0",
        json={"success": True, "result": {"count": 6, "results": [
            {"id": "c2b04a36-7e1e-4529-bc04-eb8c4dd0e46c", "title": "Destinazione d'uso catastale"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "destinazione uso catastale", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_gov_search_circolazione_pedonale(httpx_mock):
    """GOV-5: search aree circolazione pedonale."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=circolazione+pedonale&rows=5&start=0",
        json={"success": True, "result": {"count": 3, "results": [
            {"id": "9e4f3b83-bc1e-4e2e-972c-490c0965d2e0", "title": "Aree di circolazione pedonale"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "circolazione pedonale", "rows": 5, "start": 0})
    assert r["count"] >= 1


# ══════════════════════════════════════════════════════════════════════════════
#  THEME 7 — SALUTE  (1134 datasets)
# ══════════════════════════════════════════════════════════════════════════════


async def test_sal_show_turni_farmacie(httpx_mock):
    """SAL-1: turni farmacie Firenze – all url-only (WMS, KML, SHP)."""
    ds_id = "36192da7-1b8f-4a7e-922e-f44ff405f5f2"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Turni Farmacie",
            "resources": [
                {"id": "r1", "format": "WMS", "url": "https://tms.comune.fi.it/wms"},
                {"id": "r2", "format": "KML", "url": "https://data.comune.fi.it/farmacie.kml"},
                {"id": "r3", "format": "SHP", "url": "https://data.comune.fi.it/farmacie.shp"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 0
    assert len(uo) == 3


async def test_sal_show_tassi_assenze(httpx_mock):
    """SAL-2: tassi assenze ASL Taranto – CSV downloadable, XLSX url-only."""
    ds_id = "c2561d08-d7af-43b1-8f0c-ab20337aad05"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Tassi di assenze personale ASL Taranto - 2019",
            "resources": [
                {"id": "r1", "format": "CSV", "url": "https://dati.puglia.it/assenze.csv"},
                {"id": "r2", "format": "XLSX", "url": "https://dati.puglia.it/assenze.xlsx"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1 and dl[0]["format"] == "CSV"
    assert len(uo) == 1 and uo[0]["format"] == "XLSX"


async def test_sal_search_progetti_aress(httpx_mock):
    """SAL-3: search progetti AReSS Puglia."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=progetti+AReSS+Puglia&rows=5&start=0",
        json={"success": True, "result": {"count": 1, "results": [
            {"id": "0ca68f48-f7eb-4507-b95b-f92a128bec21", "title": "Progetti nazionali ed europei AReSS Puglia"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "progetti AReSS Puglia", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_sal_show_pazienti_diabete(httpx_mock):
    """SAL-4: pazienti cronici diabete – CSV only."""
    ds_id = "f57dea4b-ad4a-40d9-b819-09802798bdce"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Pazienti cronici affetti da diabete (2006-2019)",
            "resources": [
                {"id": "r1", "format": "CSV", "url": "https://dati.puglia.it/diabete.csv"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1
    assert len(uo) == 0


async def test_sal_show_breast_unit(httpx_mock):
    """SAL-5: Anagrafica Breast Unit – JSON, GeoJSON, CSV all downloadable."""
    ds_id = "1425110c-cac1-451c-9037-78fb87407378"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Anagrafica Breast Unit Puglia",
            "resources": [
                {"id": "r1", "format": "JSON", "url": "https://dati.puglia.it/breast.json"},
                {"id": "r2", "format": "GeoJSON", "url": "https://dati.puglia.it/breast.geojson"},
                {"id": "r3", "format": "CSV", "url": "https://dati.puglia.it/breast.csv"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 3  # all downloadable
    assert len(uo) == 0


# ══════════════════════════════════════════════════════════════════════════════
#  THEME 8 — TEMATICHE INTERNAZIONALI  (55 datasets)
# ══════════════════════════════════════════════════════════════════════════════


async def test_int_search_interreg(httpx_mock):
    """INT-1: search progetti Interreg pugliesi."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=interreg+pugliesi&rows=5&start=0",
        json={"success": True, "result": {"count": 3, "results": [
            {"id": "5a6a8aaa-04f7-42db-99e4-09e573b0a1d3", "title": "Progetti Interreg Pugliesi"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "interreg pugliesi", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_int_search_protocolli_intesa(httpx_mock):
    """INT-2: search protocolli di intesa."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=protocolli+intesa&rows=5&start=0",
        json={"success": True, "result": {"count": 2, "results": [
            {"id": "686d9683-51fc-41e6-b4f8-f80895d0f30e", "title": "Protocolli di intesa attivi 2014"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "protocolli intesa", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_int_show_progetti_finanziati(httpx_mock):
    """INT-3: progetti finanziati – XLS url-only, CSV downloadable."""
    ds_id = "e7438c72-f530-4d31-ae87-762d5e0aa469"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Progetti finanziati e relativi partners",
            "resources": [
                {"id": "r1", "format": "XLS", "url": "https://example.org/progetti.xls"},
                {"id": "r2", "format": "CSV", "url": "https://example.org/progetti.csv"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1 and dl[0]["format"] == "CSV"
    assert len(uo) == 1 and uo[0]["format"] == "XLS"


async def test_int_show_osservatorio_milano(httpx_mock):
    """INT-4: Osservatorio Milano Benchmark – CSV only."""
    ds_id = "6f0cfb53-742d-4044-b4ee-e0d67bffa68d"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Osservatorio Milano - Benchmark",
            "resources": [
                {"id": "r1", "format": "CSV", "url": "https://dati.comune.milano.it/benchmark.csv"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1
    assert len(uo) == 0


async def test_int_show_beneficiari_interreg(httpx_mock):
    """INT-5: beneficiari Interreg IPA – CSV downloadable, XLSX url-only."""
    ds_id = "f0c39e71-ec69-422a-922f-65fbeb4440a8"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Beneficiari Interreg IPA South Adriatic",
            "resources": [
                {"id": "r1", "format": "CSV", "url": "https://dati.puglia.it/benef.csv"},
                {"id": "r2", "format": "XLSX", "url": "https://dati.puglia.it/benef.xlsx"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1
    assert len(uo) == 1


# ══════════════════════════════════════════════════════════════════════════════
#  THEME 9 — GIUSTIZIA E SICUREZZA  (708 datasets)
# ══════════════════════════════════════════════════════════════════════════════


async def test_giu_show_incidenti_2016(httpx_mock):
    """GIU-1: statistica incidenti 2016 – CSV downloadable, XLS url-only."""
    ds_id = "75355832-91da-462a-b007-7072bc9d7c49"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "statistica C.d.s. incidenti 2016",
            "resources": [
                {"id": "r1", "format": "XLS", "url": "http://goo.gl/iqcDEP"},
                {"id": "r2", "format": "CSV", "url": "http://goo.gl/EsXa3S"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1 and dl[0]["format"] == "CSV"
    assert len(uo) == 1 and uo[0]["format"] == "XLS"


async def test_giu_search_localita_verbali(httpx_mock):
    """GIU-2: search località verbali."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=localita+verbali+incidenti&rows=5&start=0",
        json={"success": True, "result": {"count": 2, "results": [
            {"id": "0da52534-5b6a-44be-bc30-86142901f81d", "title": "statistica C.d.s. località verbali 2016"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "localita verbali incidenti", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_giu_search_violazioni(httpx_mock):
    """GIU-3: search violazioni codice della strada."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=violazioni+codice+strada&rows=5&start=0",
        json={"success": True, "result": {"count": 4, "results": [
            {"id": "472d6d29-0395-4c81-b5df-86f5acc6e4a1", "title": "statistica C.d.s.violazioni verbali 2016"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "violazioni codice strada", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_giu_search_sanzioni_ambientali(httpx_mock):
    """GIU-4: search sanzioni ambientali."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=sanzioni+ambientali&rows=5&start=0",
        json={"success": True, "result": {"count": 1, "results": [
            {"id": "735bc7fc-edff-4233-9170-88f240dc0a6c",
             "title": "Serie storica annuale delle sanzioni ambientali"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "sanzioni ambientali", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_giu_show_photored(httpx_mock):
    """GIU-5: ubicazione Photored – CSV only."""
    ds_id = "df718a8e-b5fd-49da-9d2e-7df85a48d904"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Ubicazione Photored territorio comunale",
            "resources": [
                {"id": "r1", "format": "CSV", "url": "https://goo.gl/VGiI0Q"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1
    assert len(uo) == 0


# ══════════════════════════════════════════════════════════════════════════════
#  THEME 10 — REGIONI E CITTÀ  (4888 datasets)
# ══════════════════════════════════════════════════════════════════════════════


async def test_reg_show_toponimi_firenze(httpx_mock):
    """REG-1: toponimi Firenze – CSV downloadable."""
    ds_id = "1a41df44-0d84-470c-ab5a-20999be49b2e"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Toponimi",
            "resources": [
                {"id": "r1", "format": "CSV", "url": "https://data.comune.fi.it/toponimi.csv"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1


async def test_reg_show_tratti_stradali(httpx_mock):
    """REG-2: tratti stradali Firenze – KML, SHP, WMS url-only."""
    ds_id = "e3f0f45c-4620-4d44-9188-177947f2bd56"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Tratti stradali",
            "resources": [
                {"id": "r1", "format": "KML", "url": "https://data.comune.fi.it/strade.kml"},
                {"id": "r2", "format": "SHP", "url": "https://data.comune.fi.it/strade.shp"},
                {"id": "r3", "format": "WMS", "url": "https://tms.comune.fi.it/wms"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 0
    assert len(uo) == 3


async def test_reg_show_civici(httpx_mock):
    """REG-3: civici Firenze – SHP, WMS url-only."""
    ds_id = "92d4df68-0f52-4f9c-8009-5b468734a3c9"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Civici",
            "resources": [
                {"id": "r1", "format": "SHP", "url": "https://data.comune.fi.it/civici.shp"},
                {"id": "r2", "format": "WMS", "url": "https://tms.comune.fi.it/wms"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 0
    assert len(uo) == 2


async def test_reg_search_limiti_amministrativi(httpx_mock):
    """REG-4: search limiti amministrativi comunali."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=limiti+amministrativi+comunali&rows=5&start=0",
        json={"success": True, "result": {"count": 5, "results": [
            {"id": "09d1e45c-d2e2-446d-bbd5-b120a9b84784",
             "title": "Limiti amministrativi comunali ante 2014"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "limiti amministrativi comunali", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_reg_show_carta_provinciale(httpx_mock):
    """REG-5: Carta Provinciale 1:10.000 – ZIP, WMS url-only."""
    ds_id = "9b14e2fe-2f21-4d64-8508-876c9b00ad80"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Carta Provinciale 1:10.000",
            "resources": [
                {"id": "r1", "format": "ZIP", "url": "https://dati.cittametropolitana.fi.it/carta.zip"},
                {"id": "r2", "format": "WMS", "url": "https://mappe.cittametropolitana.fi.it/wms"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 0
    assert len(uo) == 2


# ══════════════════════════════════════════════════════════════════════════════
#  THEME 11 — POPOLAZIONE E SOCIETÀ  (9100 datasets)
# ══════════════════════════════════════════════════════════════════════════════


async def test_soc_show_popolazione_quartiere(httpx_mock):
    """SOC-1: popolazione residente quartiere – CSV dl, PDF+XLSX url-only."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={POPOLAZIONE_DATASET_ID}",
        json={"success": True, "result": {
            "id": POPOLAZIONE_DATASET_ID,
            "title": "Popolazione residente per quartiere e per classe di età al 31/12/2025",
            "resources": [
                {"id": "r1", "format": "PDF", "url": "https://data.comune.fi.it/pop.pdf"},
                {"id": "r2", "format": "CSV", "url": "https://data.comune.fi.it/pop.csv"},
                {"id": "r3", "format": "XLSX", "url": "https://data.comune.fi.it/pop.xlsx"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE,
                                params={"id": POPOLAZIONE_DATASET_ID})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1 and dl[0]["format"] == "CSV"
    assert len(uo) == 2


async def test_soc_show_individui_censimento(httpx_mock):
    """SOC-2: individui residenti censimento – CSV dl, XLSX+PDF url-only."""
    ds_id = "8f42f959-54a3-4a7c-a3ae-8ff6c0974ef4"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Individui residenti per sezione di censimento",
            "resources": [
                {"id": "r1", "format": "XLSX", "url": "https://data.comune.fi.it/ind.xlsx"},
                {"id": "r2", "format": "PDF", "url": "https://data.comune.fi.it/ind.pdf"},
                {"id": "r3", "format": "CSV", "url": "https://data.comune.fi.it/ind.csv"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1
    assert len(uo) == 2


async def test_soc_show_famiglie_censimento(httpx_mock):
    """SOC-3: famiglie residenti censimento – CSV dl, PDF+XLSX url-only."""
    ds_id = "53521a7f-1a94-491b-9aa6-4acfc174e9a0"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Famiglie residenti per sezione di censimento",
            "resources": [
                {"id": "r1", "format": "PDF", "url": "https://data.comune.fi.it/fam.pdf"},
                {"id": "r2", "format": "CSV", "url": "https://data.comune.fi.it/fam.csv"},
                {"id": "r3", "format": "XLSX", "url": "https://data.comune.fi.it/fam.xlsx"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1
    assert len(uo) == 2


async def test_soc_show_stalli_disabili(httpx_mock):
    """SOC-4: stalli sosta disabili – all url-only (SHP, KML, WMS)."""
    ds_id = "01a508c5-a5d0-420b-b7c9-8eb5e437978f"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Stalli di sosta riservati ai disabili",
            "resources": [
                {"id": "r1", "format": "SHP", "url": "https://data.comune.fi.it/stalli.shp"},
                {"id": "r2", "format": "KML", "url": "https://data.comune.fi.it/stalli.kml"},
                {"id": "r3", "format": "WMS", "url": "https://tms.comune.fi.it/wms"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 0
    assert len(uo) == 3


async def test_soc_search_movimenti_turistici(httpx_mock):
    """SOC-5: search movimenti turistici Firenze."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=movimenti+turistici+Firenze&rows=5&start=0",
        json={"success": True, "result": {"count": 8, "results": [
            {"id": "375a912f-d71c-4770-affa-867eb99d1e74",
             "title": "Movimenti turistici e consistenza delle strutture ricettive 2015"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "movimenti turistici Firenze", "rows": 5, "start": 0})
    assert r["count"] >= 1


# ══════════════════════════════════════════════════════════════════════════════
#  THEME 12 — SCIENZA E TECNOLOGIA  (2631 datasets)
# ══════════════════════════════════════════════════════════════════════════════


async def test_sci_show_wifi_firenze(httpx_mock):
    """SCI-1: Wifi Firenze – WMS, SHP, KML all url-only."""
    ds_id = "8d829c58-1a8f-43e6-90ff-f2838ffe572c"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Wifi",
            "resources": [
                {"id": "r1", "format": "WMS", "url": "https://tms.comune.fi.it/wms"},
                {"id": "r2", "format": "SHP", "url": "https://data.comune.fi.it/wifi.shp"},
                {"id": "r3", "format": "KML", "url": "https://data.comune.fi.it/wifi.kml"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 0
    assert len(uo) == 3


async def test_sci_show_reti_laboratori(httpx_mock):
    """SCI-2: Reti di Laboratori – CSV+JSON downloadable, XLS+ODS url-only."""
    ds_id = "2ee92e8c-1b41-4ff0-9251-58e6b8e8b7a9"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Reti di Laboratori",
            "resources": [
                {"id": "r1", "format": "XLS", "url": "https://dati.puglia.it/lab.xls"},
                {"id": "r2", "format": "CSV", "url": "https://dati.puglia.it/lab.csv"},
                {"id": "r3", "format": "ODS", "url": "https://dati.puglia.it/lab.ods"},
                {"id": "r4", "format": "JSON", "url": "https://dati.puglia.it/lab.json"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 2  # CSV + JSON
    assert len(uo) == 2  # XLS + ODS


async def test_sci_search_digital_divide(httpx_mock):
    """SCI-3: search digital divide."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=digital+divide&rows=5&start=0",
        json={"success": True, "result": {"count": 2, "results": [
            {"id": "e66aab22-3f50-497f-9485-94d0b5a8dfc9", "title": "Digital Divide 2023"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "digital divide", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_sci_show_distretti_tecnologici(httpx_mock):
    """SCI-4: distretti tecnologici – CSV downloadable, ODS+XML+XSD url-only."""
    ds_id = "6602d578-a23a-497c-a876-5e1a663eb4d7"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Distretti tecnologici",
            "resources": [
                {"id": "r1", "format": "ODS", "url": "https://dati.puglia.it/distretti.ods"},
                {"id": "r2", "format": "CSV", "url": "https://dati.puglia.it/distretti.csv"},
                {"id": "r3", "format": "XML", "url": "https://dati.puglia.it/distretti.xml"},
                {"id": "r4", "format": "XSD", "url": "https://dati.puglia.it/distretti.xsd"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1  # CSV
    assert len(uo) == 3  # ODS, XML, XSD


async def test_sci_show_prezzario_puglia(httpx_mock):
    """SCI-5: Prezzario Puglia 2024 – CSV only."""
    ds_id = "ce05f6aa-588a-4220-8497-fb855676f7f2"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Prezzario Regione Puglia 2024",
            "resources": [
                {"id": "r1", "format": "CSV", "url": "https://dati.puglia.it/prezzario.csv"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1
    assert len(uo) == 0


# ══════════════════════════════════════════════════════════════════════════════
#  THEME 13 — TRASPORTI  (2439 datasets)
# ══════════════════════════════════════════════════════════════════════════════


async def test_tra_search_trasporto_pubblico(httpx_mock):
    """TRA-1: search trasporto pubblico tempo reale."""
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_search?q=trasporto+pubblico+tempo+reale&rows=5&start=0",
        json={"success": True, "result": {"count": 2, "results": [
            {"id": "d9c412ea-a7bc-4094-901b-7096a5546139",
             "title": "Regione Toscana - Trasporto pubblico in tempo reale"},
        ]}},
    )
    async with CkanClient() as c:
        r = await c.action("package_search", base_url=DATI_GOV_BASE,
                           params={"q": "trasporto pubblico tempo reale", "rows": 5, "start": 0})
    assert r["count"] >= 1


async def test_tra_show_incidentalita(httpx_mock):
    """TRA-2: incidentalità ciclabile – GeoJSON downloadable, rest url-only."""
    ds_id = "ebe2ac23-ca77-485b-9504-38bc49e270e6"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Incidentalità",
            "resources": [
                {"id": "r1", "format": "ZIP", "url": "https://pistoia.ldpgis.it/inc.zip"},
                {"id": "r2", "format": "GML", "url": "https://pistoia.ldpgis.it/inc.gml"},
                {"id": "r3", "format": "GeoJSON", "url": "https://pistoia.ldpgis.it/inc.geojson"},
                {"id": "r4", "format": "KML", "url": "https://pistoia.ldpgis.it/inc.kml"},
                {"id": "r5", "format": "SHP", "url": "https://pistoia.ldpgis.it/inc.shp"},
                {"id": "r6", "format": "WFS", "url": "https://pistoia.ldpgis.it/wfs"},
                {"id": "r7", "format": "WMS", "url": "https://pistoia.ldpgis.it/wms"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1 and dl[0]["format"] == "GeoJSON"
    assert len(uo) == 6


async def test_tra_show_ciclostazioni(httpx_mock):
    """TRA-3: ciclostazioni Pistoia – GeoJSON downloadable."""
    ds_id = "e83ac204-fdb8-4d8e-89d4-a8f5bec8daa6"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Ciclostazioni",
            "resources": [
                {"id": "r1", "format": "ZIP", "url": "https://pistoia.ldpgis.it/ciclo.zip"},
                {"id": "r2", "format": "GeoJSON", "url": "https://pistoia.ldpgis.it/ciclo.geojson"},
                {"id": "r3", "format": "KML", "url": "https://pistoia.ldpgis.it/ciclo.kml"},
                {"id": "r4", "format": "SHP", "url": "https://pistoia.ldpgis.it/ciclo.shp"},
                {"id": "r5", "format": "WFS", "url": "https://pistoia.ldpgis.it/wfs"},
                {"id": "r6", "format": "WMS", "url": "https://pistoia.ldpgis.it/wms"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1
    assert len(uo) == 5


async def test_tra_show_viabilita_pistoia(httpx_mock):
    """TRA-4: viabilità Pistoia – GeoJSON downloadable."""
    ds_id = "d3c26225-85c2-4c78-8f60-a2e6c2203f82"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Viabilità della Provincia di Pistoia",
            "resources": [
                {"id": "r1", "format": "ZIP", "url": "https://pistoia.ldpgis.it/viab.zip"},
                {"id": "r2", "format": "GML", "url": "https://pistoia.ldpgis.it/viab.gml"},
                {"id": "r3", "format": "GeoJSON", "url": "https://pistoia.ldpgis.it/viab.geojson"},
                {"id": "r4", "format": "KML", "url": "https://pistoia.ldpgis.it/viab.kml"},
                {"id": "r5", "format": "SHP", "url": "https://pistoia.ldpgis.it/viab.shp"},
                {"id": "r6", "format": "WFS", "url": "https://pistoia.ldpgis.it/wfs"},
                {"id": "r7", "format": "WMS", "url": "https://pistoia.ldpgis.it/wms"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 1
    assert len(uo) == 6


async def test_tra_show_svincoli_fipili(httpx_mock):
    """TRA-5: svincoli FIPILI Firenze – WMS+ZIP url-only."""
    ds_id = "480fb1df-2c52-442e-a7d0-397316213538"
    httpx_mock.add_response(
        method="GET",
        url=f"{DATI_GOV_BASE}/api/3/action/package_show?id={ds_id}",
        json={"success": True, "result": {
            "id": ds_id, "title": "Svincoli FIPILI - Città Metropolitana di Firenze",
            "resources": [
                {"id": "r1", "format": "WMS", "url": "https://mappe.cittametropolitana.fi.it/wms"},
                {"id": "r2", "format": "ZIP", "url": "https://dati.cittametropolitana.fi.it/fipili.zip"},
            ],
        }},
    )
    async with CkanClient() as c:
        result = await c.action("package_show", base_url=DATI_GOV_BASE, params={"id": ds_id})
    dl, uo = _classify_resources(result["resources"])
    assert len(dl) == 0
    assert len(uo) == 2
