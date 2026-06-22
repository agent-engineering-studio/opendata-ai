"""Test del connettore Istruzione (MIUR Open Data — anagrafe scuole).

Join DETERMINISTICO: codice ISTAT → codice catastale Belfiore (tabella statica
`data/istat_catastale.csv`, reale) → filtro su `CODICECOMUNESCUOLA`. Mapping reali
usati: 072021→E038 (Gioia del Colle), 015146→F205 (Milano), 058091→H501 (Roma).
"""

from __future__ import annotations

from pytest_httpx import HTTPXMock

from opendata_core.miur import fetch_scuole_comune
from opendata_core.miur import scuole

_BASE = "https://dati.istruzione.it/opendata/opendata/catalogo/elements1"
_HDR = "ANNOSCOLASTICO,CODICECOMUNESCUOLA,DESCRIZIONECOMUNE,DESCRIZIONETIPOLOGIAGRADOISTRUZIONESCUOLA,CODICESCUOLA"

# E038 = Gioia del Colle (ISTAT 072021); F205 = Milano (omonimia non più un problema:
# il join è per codice catastale, non per nome).
_STATALI = "\n".join([
    _HDR,
    "202526,E038,GIOIA DEL COLLE,SCUOLA INFANZIA,BAAA1",
    "202526,E038,GIOIA DEL COLLE,SCUOLA PRIMARIA,BAEE1",
    "202526,E038,GIOIA DEL COLLE,SCUOLA PRIMO GRADO,BAMM1",
    "202526,E038,GIOIA DEL COLLE,LICEO SCIENTIFICO,BAPS1",
    "202526,E038,GIOIA DEL COLLE,ISTITUTO COMPRENSIVO,BAIC1",   # aggregatore → escluso
    "202526,F205,MILANO,SCUOLA PRIMARIA,MIEE9",                 # altro comune → non contato
]) + "\n"

_PARITARIE = "\n".join([
    _HDR,
    "202526,E038,GIOIA DEL COLLE,SCUOLA INFANZIA NON STATALE,BA1A",
]) + "\n"

_HTML = "<!DOCTYPE html><html><body>Not found</body></html>"

# 4 dataset alunni per CODICESCUOLA. Codici di E038: statali BAEE1/BAMM1/BAPS1
# (primaria/sec) + BAAA1 (infanzia); paritaria BA1A (infanzia).
_ALU_HDR = "ANNOSCOLASTICO,CODICESCUOLA,ORDINESCUOLA,ANNOCORSOCLASSE,CLASSI,ALUNNIMASCHI,ALUNNIFEMMINE"
_INF_HDR = "ANNOSCOLASTICO,CODICESCUOLA,CLASSI,BAMBINIMASCHI,BAMBINIFEMMINE"
# primaria+sec statali → s_ps = 18+10+30 = 58
_ALU_PS_STATALI = "\n".join([
    _ALU_HDR,
    "202526,BAEE1,SCUOLA PRIMARIA,1,1,10,8",
    "202526,BAMM1,SCUOLA PRIMO GRADO,1,1,5,5",
    "202526,BAPS1,LICEO SCIENTIFICO,2,1,20,10",
    "202526,MIEE9,SCUOLA PRIMARIA,1,1,3,3",   # Milano (F205) → non sommato per E038
]) + "\n"
# primaria+sec paritarie → nessun codice paritario di E038 qui → p_ps = 0
_ALU_PS_PARITARIE = "\n".join([
    _ALU_HDR,
    "202526,RM1H00100,SCUOLA SECONDARIA II GRADO,1,1,5,5",
]) + "\n"
# infanzia statali (BAAA1) → s_inf = 15+10 = 25
_INF_STATALI = "\n".join([_INF_HDR, "202526,BAAA1,3,15,10"]) + "\n"
# infanzia paritarie (BA1A) → p_inf = 8+6 = 14
_INF_PARITARIE = "\n".join([_INF_HDR, "202526,BA1A,2,8,6"]) + "\n"


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


def _mock_alunni(httpx_mock: HTTPXMock, *, as_compact: str, ref: str) -> None:
    # ref alunni = {anno_fine}0831 (convenzione diversa dall'anagrafe). 4 dataset.
    for short, body in (
        ("ALUCORSOINDCLASTA", _ALU_PS_STATALI),
        ("ALUCORSOINDCLAPAR", _ALU_PS_PARITARIE),
        ("INFANZIACLASTA", _INF_STATALI),
        ("INFANZIACLAPAR", _INF_PARITARIE),
    ):
        httpx_mock.add_response(
            url=f"{_BASE}/{short}{as_compact}{ref}.csv", text=body, is_reusable=True
        )


async def test_fetch_scuole_comune_happy(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock_year(httpx_mock, statali=_STATALI, paritarie=_PARITARIE, as_compact="202526", ref="20250901")
    _mock_alunni(httpx_mock, as_compact="202526", ref="20260831")
    res = await fetch_scuole_comune("072021", start_year=2025)  # ISTAT → E038

    assert res["trovato"] is True
    assert res["anno_scolastico"] == "2025/26"
    # IC escluso; Milano (F205) NON contato (join per codice, non per nome).
    assert res["per_ordine"]["infanzia"] == 2      # 1 statale + 1 paritaria
    assert res["per_ordine"]["primaria"] == 1
    assert res["per_ordine"]["secondaria_i"] == 1
    assert res["per_ordine"]["secondaria_ii"] == 1  # liceo scientifico
    assert res["scuole_statali"] == 4
    assert res["scuole_paritarie"] == 1
    # Alunni: s_ps=58, s_inf=25, p_ps=0, p_inf=14.
    assert res["alunni_totali"] == 97           # 58 + 0 + 25 + 14
    assert res["alunni_infanzia"] == 39         # 25 + 14
    assert res["alunni_paritarie"] == 14        # 0 + 14
    assert res["alunni_statali"] == 83          # 58 + 25 (statali, tutti gli ordini)
    assert res["alunni_anno"] == "2025/26"
    assert "SCUANAGRAFESTAT20252620250901.csv" in res["source_url"]
    assert res["sources"][0]["licenza"].startswith("MIUR Open Data")


async def test_fetch_scuole_comune_absent(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock_year(httpx_mock, statali=_STATALI, paritarie=_PARITARIE, as_compact="202526", ref="20250901")
    # Roma (058091 → H501): mappato, ma assente dal CSV → trovato False.
    res = await fetch_scuole_comune("058091", start_year=2025)
    assert res["trovato"] is False
    assert "source_url" in res


async def test_fetch_scuole_comune_unmapped_istat(httpx_mock: HTTPXMock) -> None:
    _reset()
    # Codice ISTAT inesistente → non mappato a catastale → nessuna fetch, trovato False.
    res = await fetch_scuole_comune("999999", start_year=2025)
    assert res["trovato"] is False
    assert "non mappato" in res["note"]


async def test_fetch_scuole_comune_year_fallback(httpx_mock: HTTPXMock) -> None:
    _reset()
    # 2025/26 mancante (HTML con 200) → si scende al 2024/25.
    _mock_year(httpx_mock, statali=_HTML, paritarie=_HTML, as_compact="202526", ref="20250901")
    _mock_year(httpx_mock, statali=_STATALI, paritarie=_PARITARIE, as_compact="202425", ref="20240901")
    _mock_alunni(httpx_mock, as_compact="202526", ref="20260831")  # best-effort
    res = await fetch_scuole_comune("072021", start_year=2025)
    assert res["trovato"] is True
    assert res["anno_scolastico"] == "2024/25"
    assert "SCUANAGRAFESTAT20242520240901.csv" in res["source_url"]
