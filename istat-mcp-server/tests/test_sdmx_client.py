"""Unit tests for the SDMX client using pytest-httpx to stub the upstream SDMX endpoint."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from opendata_core.sdmx.client import SdmxClient, SdmxError, data_path, df_ref


def test_df_ref_is_percent_encoded() -> None:
    assert df_ref("IT1", "101_12", "1.0") == "IT1/101_12/1.0"


def test_data_path_defaults_to_all() -> None:
    assert data_path("101_12") == "data/101_12/all"
    assert data_path("101_12", "ITH5..Y_GE65") == "data/101_12/ITH5..Y_GE65"


async def test_get_json_happy_path(httpx_mock: HTTPXMock) -> None:
    base = "https://esploradati.istat.it/SDMXWS/rest"
    httpx_mock.add_response(
        url=f"{base}/dataflow",
        json={"data": {"dataflows": []}},
    )
    async with SdmxClient(base_url=base) as c:
        payload = await c.get_json("dataflow", cache=False)
    assert payload == {"data": {"dataflows": []}}


async def test_get_json_raises_on_http_error(httpx_mock: HTTPXMock) -> None:
    base = "https://esploradati.istat.it/SDMXWS/rest"
    httpx_mock.add_response(url=f"{base}/dataflow", status_code=503, text="boom")
    async with SdmxClient(base_url=base) as c:
        with pytest.raises(SdmxError):
            await c.get_json("dataflow", cache=False)
