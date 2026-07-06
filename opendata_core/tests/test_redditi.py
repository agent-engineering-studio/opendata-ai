"""Test del connettore Reddito/IRPEF (MEF Dipartimento delle Finanze, #91)."""

from __future__ import annotations

import io
import zipfile

from pytest_httpx import HTTPXMock

from opendata_core.mef import fetch_redditi_comune
from opendata_core.mef import redditi

_BASE = "https://www1.finanze.gov.it/finanze3/analisi_stat/v_4_0_0/contenuti"

# Header reale (50 colonne) + due righe: Gioia del Colle (072021) e un comune
# con reddito imponibile a frequenza zero (dato insufficiente).
_HEADER = ";".join([
    "Anno di imposta", "Codice catastale", "Codice Istat Comune", "Denominazione Comune",
    "Sigla Provincia", "Regione", "Codice Istat Regione", "Numero contribuenti",
    *(f"Col{i}" for i in range(8, 22)),  # colonne intermedie non usate dal connettore
    "Reddito imponibile - Frequenza", "Reddito imponibile - Ammontare in euro",
    *(f"Col{i}" for i in range(24, 34)),  # altre colonne intermedie non usate
    "Reddito complessivo <=0 - Frequenza", "Reddito complessivo <=0 - Ammontare",
    "Reddito complessivo 0-10k - Frequenza", "Reddito complessivo 0-10k - Ammontare",
    "Reddito complessivo 10k-15k - Frequenza", "Reddito complessivo 10k-15k - Ammontare",
    "Reddito complessivo 15k-26k - Frequenza", "Reddito complessivo 15k-26k - Ammontare",
    "Reddito complessivo 26k-55k - Frequenza", "Reddito complessivo 26k-55k - Ammontare",
    "Reddito complessivo 55k-75k - Frequenza", "Reddito complessivo 55k-75k - Ammontare",
    "Reddito complessivo 75k-120k - Frequenza", "Reddito complessivo 75k-120k - Ammontare",
    "Reddito complessivo oltre120k - Frequenza", "Reddito complessivo oltre120k - Ammontare",
])


def _row(cod_istat: str, nome: str, n_contribuenti: str, imp_freq: str, imp_amount: str) -> str:
    intermedie1 = ";".join(["0"] * 14)  # colonne 8-21
    intermedie2 = ";".join(["0"] * 10)  # colonne 24-33
    fasce = ";".join(["100", "1000000", "200", "2000000", "150", "2500000",
                       "300", "8000000", "250", "10000000", "50", "3000000",
                       "45", "3500000", "20", "3000000"])  # 8 fasce (freq;ammontare)
    return (
        f"2022;E999;{cod_istat};{nome};BA;Puglia;16;{n_contribuenti};{intermedie1};"
        f"{imp_freq};{imp_amount};{intermedie2};{fasce}"
    )


_CSV_2022 = "\n".join([
    _HEADER,
    _row("072021", "GIOIA DEL COLLE", "18191", "17005", "326992243"),
    _row("072999", "COMUNE VUOTO", "0", "0", "0"),
]) + "\n"


def _zip_bytes(csv_text: str, filename: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(filename, csv_text)
    return buf.getvalue()


def _reset() -> None:
    redditi._year_index_cache.clear()
    redditi._result_cache.clear()


async def test_fetch_redditi_happy(httpx_mock: HTTPXMock) -> None:
    _reset()
    httpx_mock.add_response(
        url=f"{_BASE}/Redditi_e_principali_variabili_IRPEF_su_base_comunale_CSV_2022.zip",
        content=_zip_bytes(_CSV_2022, "redditi_2022.csv"), is_reusable=True,
    )
    res = await fetch_redditi_comune("072021", anno=2022)
    assert res["trovato"] is True
    assert res["anno"] == "2022"
    assert res["numero_contribuenti"] == 18191
    assert res["reddito_medio_imponibile"] == round(326992243 / 17005, 0)
    assert res["quota_fascia_bassa_pct"] is not None
    assert res["quota_fascia_alta_pct"] is not None
    assert res["source_url"].endswith("2022.zip")
    assert res["sources"][0]["licenza"].startswith("MEF")


async def test_fetch_redditi_comune_assente(httpx_mock: HTTPXMock) -> None:
    _reset()
    httpx_mock.add_response(
        url=f"{_BASE}/Redditi_e_principali_variabili_IRPEF_su_base_comunale_CSV_2022.zip",
        content=_zip_bytes(_CSV_2022, "redditi_2022.csv"), is_reusable=True,
    )
    res = await fetch_redditi_comune("999999", anno=2022)
    assert res["trovato"] is False
    assert res["anno"] == "2022"


async def test_fetch_redditi_frequenza_zero_insufficiente(httpx_mock: HTTPXMock) -> None:
    _reset()
    httpx_mock.add_response(
        url=f"{_BASE}/Redditi_e_principali_variabili_IRPEF_su_base_comunale_CSV_2022.zip",
        content=_zip_bytes(_CSV_2022, "redditi_2022.csv"), is_reusable=True,
    )
    res = await fetch_redditi_comune("072999", anno=2022)
    assert res["trovato"] is False


async def test_fetch_redditi_year_fallback_on_404(httpx_mock: HTTPXMock) -> None:
    """L'anno richiesto non è ancora pubblicato (404) → retrocede all'anno precedente."""
    _reset()
    httpx_mock.add_response(
        url=f"{_BASE}/Redditi_e_principali_variabili_IRPEF_su_base_comunale_CSV_2023.zip",
        status_code=404,
    )
    httpx_mock.add_response(
        url=f"{_BASE}/Redditi_e_principali_variabili_IRPEF_su_base_comunale_CSV_2022.zip",
        content=_zip_bytes(_CSV_2022, "redditi_2022.csv"), is_reusable=True,
    )
    res = await fetch_redditi_comune("072021", anno=2023)
    assert res["trovato"] is True
    assert res["anno"] == "2022"  # retrocesso


async def test_fetch_redditi_nessun_anno_disponibile(httpx_mock: HTTPXMock) -> None:
    _reset()
    # start_year=2023, _YEARS_BACK=5 → prova 2023..2018 (6 anni) prima di arrendersi.
    for y in range(2023, 2017, -1):
        httpx_mock.add_response(
            url=f"{_BASE}/Redditi_e_principali_variabili_IRPEF_su_base_comunale_CSV_{y}.zip",
            status_code=404,
        )
    res = await fetch_redditi_comune("072021", anno=2023)
    assert res["trovato"] is False
    assert "anno" not in res
