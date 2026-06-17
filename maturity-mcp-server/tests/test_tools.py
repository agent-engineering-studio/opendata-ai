"""Test dei tool maturity-mcp con CKAN mockato (pytest-httpx) e Haiku assente.

Senza ANTHROPIC_API_KEY il semantico è saltato → assessment deterministico.
"""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from maturity_mcp.tools import _assess, _quality_dict, _result_dict
from opendata_core.maturity import DatasetInput, assess_quality

_ORG = {"id": "org-gdc", "name": "comune-di-gioia-del-colle", "title": "Comune di Gioia del Colle"}


def _package(i: int, *, good: bool) -> dict:
    if good:
        return {
            "id": f"good-{i}", "title": f"Statistiche {i}", "notes": "Descrizione chiara.",
            "tags": [{"name": "statistica"}], "theme": "POP", "license_id": "cc-by-4.0",
            "isopen": True, "metadata_modified": "2026-04-01T00:00:00", "frequency": "annual",
            "resources": [{"format": "CSV", "url": f"https://ex.it/{i}.csv"}],
        }
    return {
        "id": f"bad-{i}", "title": f"Doc {i}", "notes": "", "tags": [], "isopen": False,
        "metadata_modified": "2021-01-01T00:00:00",
        "resources": [{"format": "PDF", "url": f"https://ex.it/{i}.pdf"}],
    }


@pytest.fixture(autouse=True)
def _no_anthropic(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


async def test_assess_pipeline_with_mocked_ckan(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(json={"success": True, "result": _ORG})
    packages = [_package(i, good=True) for i in range(3)] + [_package(i, good=False) for i in range(2)]
    httpx_mock.add_response(json={"success": True, "result": {"count": 5, "results": packages}})

    harvest, result = await _assess("comune-di-gioia-del-colle", None, 50, use_semantic=False)

    assert harvest.ckan_org_id == "org-gdc"
    assert result.n_datasets == 5
    body = _result_dict(harvest, result)
    assert body["entity"] == "comune-di-gioia-del-colle"
    assert 0.0 <= body["scores"]["overall"] <= 100.0
    assert body["scores"]["level"] in {"Beginner", "Follower", "Fast-tracker", "Trend-setter"}
    # i dataset 'bad' generano raccomandazioni
    assert any(r["code"] == "open_license" for r in body["recommendations"])


async def test_truncation_flag(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(json={"success": True, "result": _ORG})
    httpx_mock.add_response(
        json={"success": True, "result": {"count": 120, "results": [_package(0, good=True)]}}
    )
    harvest, _ = await _assess("org", None, 1, use_semantic=False)
    assert harvest.total == 120
    assert harvest.truncated is True


def test_quality_dict_shape() -> None:
    ds = DatasetInput.from_ckan(_package(1, good=True))
    d = _quality_dict(assess_quality(ds))
    assert set(d) >= {"dataset_id", "stars_5", "fair", "dcat_ap_it", "iso25012", "hvd_category"}
    assert d["fair"]["mean"] >= 0.0
