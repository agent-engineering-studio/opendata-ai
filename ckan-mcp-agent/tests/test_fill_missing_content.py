"""Unit tests for _fill_missing_content: which formats trigger a download."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ckan_agent.api import Resource, _fill_missing_content


def _make(fmt: str, content: str | None = None) -> Resource:
    return Resource(
        name=f"file.{fmt.lower()}",
        url=f"https://example.com/file.{fmt.lower()}",
        format=fmt,
        content=content,
    )


@pytest.mark.asyncio
async def test_downloads_csv_json_geojson_txt():
    resources = [_make(f) for f in ("CSV", "JSON", "GEOJSON", "TXT")]
    with patch("ckan_agent.api._fetch_text", new_callable=AsyncMock) as fetch:
        fetch.return_value = "DATA"
        await _fill_missing_content(resources)
    assert all(r.content == "DATA" for r in resources)
    assert fetch.call_count == 4


@pytest.mark.asyncio
async def test_downloads_xml_rdf_kml_wms_wfs_wcs():
    resources = [_make(f) for f in ("XML", "RDF", "KML", "WMS", "WFS", "WCS")]
    with patch("ckan_agent.api._fetch_text", new_callable=AsyncMock) as fetch:
        fetch.return_value = "<root/>"
        await _fill_missing_content(resources)
    assert all(r.content == "<root/>" for r in resources)
    assert fetch.call_count == 6


@pytest.mark.asyncio
async def test_skips_binary_formats():
    resources = [_make(f) for f in ("PDF", "XLSX", "ZIP", "SHP")]
    with patch("ckan_agent.api._fetch_text", new_callable=AsyncMock) as fetch:
        await _fill_missing_content(resources)
    assert all(r.content is None for r in resources)
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_skips_when_content_already_present():
    resources = [_make("CSV", content="already,here")]
    with patch("ckan_agent.api._fetch_text", new_callable=AsyncMock) as fetch:
        await _fill_missing_content(resources)
    assert resources[0].content == "already,here"
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_format_match_is_case_insensitive():
    resources = [_make("xml"), _make("Csv")]
    with patch("ckan_agent.api._fetch_text", new_callable=AsyncMock) as fetch:
        fetch.return_value = "X"
        await _fill_missing_content(resources)
    assert fetch.call_count == 2
