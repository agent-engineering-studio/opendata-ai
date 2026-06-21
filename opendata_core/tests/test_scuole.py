"""Test del connettore Istruzione (MIUR Open Data — anagrafe scuole)."""

from __future__ import annotations

from pytest_httpx import HTTPXMock

from opendata_core.miur import fetch_scuole_comune
from opendata_core.miur import scuole

_BASE = "https://dati.istruzione.it/opendata/opendata/catalogo/elements1"
_HDR = "ANNOSCOLASTICO,REGIONE,DESCRIZIONECOMUNE,DESCRIZIONETIPOLOGIAGRADOISTRUZIONESCUOLA,CODICESCUOLA"

# Gioia del Colle (PUGLIA) + un omonimo sintetico in LOMBARDIA + un IC da escludere.
_STATALI = "\n".join([
    _HDR,
    "202526,PUGLIA,GIOIA DEL COLLE,SCUOLA INFANZIA,BAAA1",
    "202526,PUGLIA,GIOIA DEL COLLE,SCUOLA PRIMARIA,BAEE1",
    "202526,PUGLIA,GIOIA DEL COLLE,SCUOLA PRIMO GRADO,BAMM1",
    "202526,PUGLIA,GIOIA DEL COLLE,LICEO SCIENTIFICO,BAPS1",
    "202526,PUGLIA,GIOIA DEL COLLE,ISTITUTO COMPRENSIVO,BAIC1",   # aggregatore → escluso
    "202526,LOMBARDIA,GIOIA DEL COLLE,SCUOLA PRIMARIA,MIEE9",     # omonimo (disambiguazione)
    "202526,EMILIA ROMAGNA,FORLI',SCUOLA PRIMARIA,FOEE1",         # accento/apostrofo
]) + "\n"

_PARITARIE = "\n".join([
    _HDR,
    "202526,PUGLIA,GIOIA DEL COLLE,SCUOLA INFANZIA NON STATALE,BA1A",
]) + "\n"

_HTML = "<!DOCTYPE html><html><body>Not found</body></html>"


def _reset() -> None:
    scuole._index_cache.clear()
    scuole._result_cache.clear()


def _mock_year(httpx_mock: HTTPXMock, *, statali: str, paritarie: str, as_compact: str, ref: str) -> None:
    httpx_mock.add_response(
        url=f"{_BASE}/SCUANAGRAFESTAT{as_compact}{ref}.csv", text=statali, is_reusable=True
    )
    httpx_mock.add_response(
        url=f"{_BASE}/SCUANAGRAFEPAR{as_compact}{ref}.csv", text=paritarie, is_reusable=True
    )


async def test_fetch_scuole_comune_happy(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock_year(httpx_mock, statali=_STATALI, paritarie=_PARITARIE, as_compact="202526", ref="20250901")
    res = await fetch_scuole_comune("Gioia del Colle", start_year=2025)

    assert res["trovato"] is True
    assert res["anno_scolastico"] == "2025/26"
    # IC escluso; omonimo lombardo NON sommato (manca la regione → conta solo per nome,
    # quindi senza regione l'omonimo gonfia primaria: lo verifichiamo nel test regione).
    assert res["per_ordine"]["infanzia"] == 2      # 1 statale + 1 paritaria
    assert res["per_ordine"]["secondaria_i"] == 1
    assert res["per_ordine"]["secondaria_ii"] == 1  # liceo scientifico
    assert res["scuole_paritarie"] == 1
    assert "SCUANAGRAFESTAT20252620250901.csv" in res["source_url"]
    assert res["sources"][0]["licenza"].startswith("MIUR Open Data")


async def test_fetch_scuole_comune_region_disambiguates_omonimo(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock_year(httpx_mock, statali=_STATALI, paritarie=_PARITARIE, as_compact="202526", ref="20250901")
    # Con regione PUGLIA l'omonimo lombardo (SCUOLA PRIMARIA) è escluso → primaria=1.
    res = await fetch_scuole_comune("Gioia del Colle", regione="Puglia", start_year=2025)
    assert res["trovato"] is True
    assert res["per_ordine"]["primaria"] == 1
    # Senza regione, invece, l'omonimo si somma → primaria=2 (limite noto del join per nome).
    _reset()
    _mock_year(httpx_mock, statali=_STATALI, paritarie=_PARITARIE, as_compact="202526", ref="20250901")
    res_noreg = await fetch_scuole_comune("Gioia del Colle", start_year=2025)
    assert res_noreg["per_ordine"]["primaria"] == 2


async def test_fetch_scuole_comune_accent_insensitive(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock_year(httpx_mock, statali=_STATALI, paritarie=_PARITARIE, as_compact="202526", ref="20250901")
    res = await fetch_scuole_comune("Forlì", start_year=2025)  # CSV ha "FORLI'"
    assert res["trovato"] is True
    assert res["per_ordine"]["primaria"] == 1


async def test_fetch_scuole_comune_absent(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock_year(httpx_mock, statali=_STATALI, paritarie=_PARITARIE, as_compact="202526", ref="20250901")
    res = await fetch_scuole_comune("Comune Inesistente", start_year=2025)
    assert res["trovato"] is False
    assert "source_url" in res


async def test_fetch_scuole_comune_year_fallback(httpx_mock: HTTPXMock) -> None:
    _reset()
    # 2025/26 mancante (HTML con 200) → si scende al 2024/25.
    _mock_year(httpx_mock, statali=_HTML, paritarie=_HTML, as_compact="202526", ref="20250901")
    _mock_year(httpx_mock, statali=_STATALI, paritarie=_PARITARIE, as_compact="202425", ref="20240901")
    res = await fetch_scuole_comune("Gioia del Colle", regione="Puglia", start_year=2025)
    assert res["trovato"] is True
    assert res["anno_scolastico"] == "2024/25"
    assert "SCUANAGRAFESTAT20242520240901.csv" in res["source_url"]


async def test_fetch_scuole_comune_no_name(httpx_mock: HTTPXMock) -> None:
    _reset()
    res = await fetch_scuole_comune("", start_year=2025)  # nessun nome → no join, no fetch
    assert res["trovato"] is False
