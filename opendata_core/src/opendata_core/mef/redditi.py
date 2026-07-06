"""MEF — Dipartimento delle Finanze: dichiarazioni IRPEF su base comunale (#91).

Reddito dichiarato dai contribuenti di un comune: numero di contribuenti,
reddito imponibile medio, quota nelle fasce di reddito basse/alte. Ancora la
lente socio-economica REDDITO, complementare a Lavoro/Welfare (nessuna delle
due misura il reddito dichiarato). Fonte: CSV ufficiale MEF, un file per anno
d'imposta, licenza **CC BY 3.0 IT** — verificato live (2022/2023/2024,
`www1.finanze.gov.it`, `;`-delimitato, sia codice catastale sia codice ISTAT
comune in colonna → nessuna tabella di mapping esterna necessaria, a
differenza di MIUR/Belfiore). Il file arriva zippato: la libreria standard
`zipfile` basta, nessuna dipendenza nuova.

La pubblicazione ha ~2 anni di ritardo sull'anno corrente: si prova l'anno più
recente plausibile e si retrocede finché non si trova un file esistente (404
→ anno non ancora pubblicato).
"""

from __future__ import annotations

import csv
import io
import logging
import os
import zipfile
from datetime import date
from typing import Any

import httpx
from cachetools import TTLCache

log = logging.getLogger("opendata-core.mef.redditi")

_BASE_DEFAULT = os.getenv(
    "MEF_REDDITI_BASE_URL",
    "https://www1.finanze.gov.it/finanze3/analisi_stat/v_4_0_0/contenuti",
)
_USER_AGENT = os.getenv("MEF_REDDITI_USER_AGENT", "opendata-ai/1.0 (+territorial-analysis)")
_HTTP_TIMEOUT = float(os.getenv("MEF_REDDITI_HTTP_TIMEOUT", "60"))
_FIRST_YEAR = 2000  # non si retrocede oltre: il dataset MEF parte dal 2000
_YEARS_BACK = 5  # quanti anni si tenta a ritroso dal più recente plausibile

_TTL = int(os.getenv("MEF_REDDITI_CACHE_TTL_SECONDS", str(7 * 24 * 3600)))
_year_index_cache: TTLCache = TTLCache(maxsize=8, ttl=_TTL)  # anno → {codice_istat: riga}
_result_cache: TTLCache = TTLCache(maxsize=512, ttl=_TTL)

# Indici di colonna (0-based) verificati sul CSV reale (50 colonne, header ';').
_COL_CODICE_ISTAT = 2
_COL_NUMERO_CONTRIBUENTI = 7
_COL_IMPONIBILE_FREQ = 22
_COL_IMPONIBILE_AMOUNT = 23
# Fasce di reddito complessivo: (indice_frequenza, indice_ammontare), crescenti.
_FASCE = [
    (34, 35),  # <= 0 €
    (36, 37),  # 0-10.000 €
    (38, 39),  # 10.000-15.000 €
    (40, 41),  # 15.000-26.000 €
    (42, 43),  # 26.000-55.000 €
    (44, 45),  # 55.000-75.000 €
    (46, 47),  # 75.000-120.000 €
    (48, 49),  # oltre 120.000 €
]
_FASCIA_BASSA = (0, 1, 2)  # <=0, 0-10k, 10k-15k
_FASCIA_ALTA = (6, 7)      # 75k-120k, oltre 120k


def _to_number(raw: str) -> float | None:
    s = (raw or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _url_for_year(base: str, year: int) -> str:
    return f"{base}/Redditi_e_principali_variabili_IRPEF_su_base_comunale_CSV_{year}.zip"


async def _load_year_index(
    client: httpx.AsyncClient, base: str, year: int
) -> dict[str, list[str]] | None:
    """Scarica e spacchetta il CSV di un anno; `None` se il file non esiste (404)."""
    if year in _year_index_cache:
        return _year_index_cache[year]
    try:
        resp = await client.get(_url_for_year(base, year))
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not names:
            return None
        text = zf.read(names[0]).decode("utf-8", errors="replace")
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    index: dict[str, list[str]] = {}
    for r in rows[1:]:
        if len(r) <= _COL_CODICE_ISTAT:
            continue
        cod = r[_COL_CODICE_ISTAT].strip()
        if cod:
            index[cod] = r
    _year_index_cache[year] = index
    return index


def _fascia_pct(row: list[str], idxs: tuple[int, ...], n_contribuenti: float) -> float | None:
    tot = 0.0
    any_val = False
    for i in idxs:
        freq_idx = _FASCE[i][0]
        if freq_idx < len(row):
            v = _to_number(row[freq_idx])
            if v is not None:
                tot += v
                any_val = True
    return round(100 * tot / n_contribuenti, 1) if any_val and n_contribuenti else None


async def fetch_redditi_comune(
    cod_comune: str, *, base_url: str | None = None, anno: int | None = None
) -> dict[str, Any]:
    """Reddito IRPEF dichiarato dai contribuenti di un comune (MEF, anno più recente disponibile).

    Ritorna numero di contribuenti, reddito imponibile medio per contribuente,
    quota di contribuenti nelle fasce di reddito basse (<=15.000€) e alte
    (>75.000€), con `source_url`/`sources`. Prova `anno` (o l'anno più recente
    plausibile) e retrocede fino a `_YEARS_BACK` anni se il file non è ancora
    pubblicato. Comune assente nel file → `trovato: false`.
    """
    cod = (cod_comune or "").strip()
    base = (base_url or _BASE_DEFAULT).rstrip("/")
    start_year = anno or (date.today().year - 2)  # pubblicazione con ~2 anni di ritardo
    ck = (base, cod, start_year)
    if ck in _result_cache:
        return _result_cache[ck]

    row: list[str] | None = None
    used_year: int | None = None
    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT, headers={"User-Agent": _USER_AGENT}, follow_redirects=True
    ) as client:
        for y in range(start_year, max(start_year - _YEARS_BACK, _FIRST_YEAR) - 1, -1):
            index = await _load_year_index(client, base, y)
            if index is None:
                continue
            used_year = y
            row = index.get(cod)
            break  # primo anno pubblicato trovato: lo usiamo (anche se il comune manca)

    if used_year is None:
        result = {
            "comune": cod, "trovato": False,
            "note": "Nessun file IRPEF MEF disponibile per gli anni recenti.",
        }
        _result_cache[ck] = result
        return result

    source_url = _url_for_year(base, used_year)
    if row is None or len(row) <= _COL_IMPONIBILE_AMOUNT:
        result = {
            "comune": cod, "trovato": False, "anno": str(used_year), "source_url": source_url,
            "note": f"Comune {cod} assente nel file IRPEF MEF {used_year}.",
        }
        _result_cache[ck] = result
        return result

    n_contribuenti = _to_number(row[_COL_NUMERO_CONTRIBUENTI])
    imp_freq = _to_number(row[_COL_IMPONIBILE_FREQ])
    imp_amount = _to_number(row[_COL_IMPONIBILE_AMOUNT])
    if not n_contribuenti:
        result = {
            "comune": cod, "trovato": False, "anno": str(used_year), "source_url": source_url,
            "note": f"Nessun dato IRPEF per il comune {cod} nell'anno {used_year}.",
        }
        _result_cache[ck] = result
        return result

    result = {
        "comune": cod,
        "anno": str(used_year),
        "numero_contribuenti": int(n_contribuenti),
        "reddito_medio_imponibile": round(imp_amount / imp_freq, 0) if imp_freq else None,
        "quota_fascia_bassa_pct": _fascia_pct(row, _FASCIA_BASSA, n_contribuenti),
        "quota_fascia_alta_pct": _fascia_pct(row, _FASCIA_ALTA, n_contribuenti),
        "source_url": source_url,
        "sources": [
            {
                "url": source_url,
                "estratto_il": date.today().isoformat(),
                "licenza": "MEF Dipartimento delle Finanze — CC BY 3.0 IT",
            }
        ],
        "trovato": True,
        "note": (
            f"MEF Dipartimento delle Finanze, dichiarazioni IRPEF anno d'imposta {used_year} "
            "(dato annuale, pubblicato con ~2 anni di ritardo). Reddito imponibile medio per "
            "contribuente e quota di contribuenti nelle fasce di reddito basse (<=15.000€) e "
            "alte (>75.000€)."
        ),
    }
    _result_cache[ck] = result
    return result
