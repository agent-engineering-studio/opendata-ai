"""Smoke tests for the CKAN HTTP client using pytest-httpx."""

from __future__ import annotations

import pytest

from ckan_mcp.ckan_client import CkanClient, CkanError, _normalize_base

# ─── Default base URL (dati.gov.it) ──────────────────────────────────────────

DATI_GOV_BASE = "https://www.dati.gov.it/opendata"
POPOLAZIONE_DATASET_ID = "2908fe96-58c4-40fe-8b29-9d4d78715ba7"


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
