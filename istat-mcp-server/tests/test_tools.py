"""Unit tests for the pinned ASIA commerce connector (istat_imprese_comune).

The parser is tested directly; the fetch path is exercised against a stubbed
SDMX-CSV response via pytest-httpx (the real SdmxClient.get_csv runs).
"""

from __future__ import annotations

from pytest_httpx import HTTPXMock

from istat_mcp.tools import _parse_asia_csv, fetch_imprese_comune
from opendata_core.sdmx import asia

_HDR = (
    "DATAFLOW,FREQ,REF_AREA,DATA_TYPE,ECON_ACTIVITY_NACE_2007,"
    "PERS_EMPL_SIZE_CLASS,TIME_PERIOD,OBS_VALUE"
)


def _row(dt: str, ateco: str, size: str, year: str, val: str) -> str:
    return f"DF,A: annual,072021: Gioia del Colle,{dt},{ateco},{size},{year},{val}"


# labels=both renders each dimension cell as "CODE: Label" — commas avoided so the
# hand-built fixture stays a simple CSV (the real feed quotes labels with commas).
_LU = "LU: number of local units of active enterprises"
_AD = "LUEMPDAA: persons employed of local units (annual average)"
_FIXTURE = "\n".join(
    [
        _HDR,
        # latest year 2023
        _row(_LU, "0010: TOTAL", "TOTAL: total", "2023", "2056"),
        _row(_AD, "0010: TOTAL", "TOTAL: total", "2023", "6048.34"),
        _row(_LU, "G: wholesale and retail trade", "TOTAL: total", "2023", "569"),
        _row(_AD, "G: wholesale and retail trade", "TOTAL: total", "2023", "1473.63"),
        # a non-TOTAL size class for the SAME (G, LU) — must be IGNORED (no double count)
        _row(_LU, "G: wholesale and retail trade", "W0_9: 0-9", "2023", "500"),
        _row(_LU, "I: accommodation and food service", "TOTAL: total", "2023", "200"),
        _row(_AD, "I: accommodation and food service", "TOTAL: total", "2023", "600"),
        # a sub-section (numeric ATECO) — kept in per_ateco but NOT a section letter
        _row(_LU, "461: wholesale on a fee basis", "TOTAL: total", "2023", "120"),
        # older year — must be ignored once 2023 is present
        _row(_LU, "0010: TOTAL", "TOTAL: total", "2022", "2000"),
    ]
) + "\n"

_BASE = "https://esploradati.istat.it/SDMXWS/rest"


# ─────────────────────────────── parser ───────────────────────────────

def test_parse_picks_latest_year_and_total_size_only() -> None:
    parsed = _parse_asia_csv(_FIXTURE)
    assert parsed["anno"] == "2023"
    per = parsed["per_ateco"]
    # G local units come from the TOTAL size row (569), NOT the W0_9 row (500).
    assert per["G"]["unita_locali"] == 569
    assert per["G"]["addetti"] == 1473.6  # rounded to 1 decimal
    assert per["0010"]["unita_locali"] == 2056  # latest year, not the 2022 value
    assert per["I"]["unita_locali"] == 200
    assert "461" in per  # sub-section retained at parse level


def test_parse_bad_payload_returns_empty() -> None:
    assert _parse_asia_csv("Error executing generated SQL")["per_ateco"] == {}
    assert _parse_asia_csv("")["per_ateco"] == {}


# ─────────────────────────────── fetch ────────────────────────────────

async def test_fetch_imprese_comune_happy(httpx_mock: HTTPXMock) -> None:
    asia._asia_cache.clear()
    httpx_mock.add_response(text=_FIXTURE)
    res = await fetch_imprese_comune("072021", base_url=_BASE)

    assert res["trovato"] is True
    assert res["anno"] == "2023"
    assert res["totale"]["unita_locali"] == 2056
    assert res["commercio"]["unita_locali"] == 569
    assert res["commercio"]["ateco"] == "G"
    assert res["commercio"]["quota_unita_locali_pct"] == 27.7
    # per_sezione_ateco holds only single-letter sections (G, I) — not 0010 nor 461
    assert set(res["per_sezione_ateco"]) == {"G", "I"}
    assert "183_285" in res["source_url"]
    assert "A.072021...TOTAL" in res["source_url"]
    assert res["sources"] and res["sources"][0]["licenza"].startswith("ISTAT")


async def test_fetch_imprese_comune_absent(httpx_mock: HTTPXMock) -> None:
    asia._asia_cache.clear()
    httpx_mock.add_response(text="Error executing generated SQL")
    res = await fetch_imprese_comune("999999", base_url=_BASE)

    assert res["trovato"] is False
    assert "source_url" in res
    assert "999999" in res["note"]
