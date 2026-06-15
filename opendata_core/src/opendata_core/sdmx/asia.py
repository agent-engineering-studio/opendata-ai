"""ISTAT ASIA — comune-level commerce connector (unità locali + addetti per ATECO).

Discovery by keyword on esploradati.istat.it is slow/unreliable; pinning the ASIA
dataflow + a single-comune positional key turns it into ONE small, deterministic
call. Structure verified live (2026-06): dataflow 183_285 / DSD DICA_ASIAULP
"Unità locali e addetti".

Key order (positional, TIME out of key):
    FREQ.REF_AREA.DATA_TYPE.ECON_ACTIVITY_NACE_2007.PERS_EMPL_SIZE_CLASS
→ single comune, total size class: "A.{cod}...TOTAL".

Shared by the istat-mcp tool (`istat_imprese_comune`) and the backend orchestrator,
which injects the commerce evidence deterministically (the LLM specialist proved
unreliable at surfacing it).
"""

from __future__ import annotations

import csv
import io
import os
from datetime import date, datetime, timezone
from typing import Any

from cachetools import TTLCache

from .client import SdmxClient, data_path

_ASIA_FLOW_ID = os.getenv("ASIA_FLOW_ID", "183_285")
# ATECO 2007 (CL_ATECO_2007): "0010" = all activities total; single letters = sections.
_ASIA_TOTAL_ATECO = "0010"
_ASIA_COMMERCIO_ATECO = "G"  # wholesale and retail trade — the commerce section
_ASIA_TOTAL_SIZE = "TOTAL"  # CL_CLLVT total over employee-size classes
# CL_TIPO_DATO_CIS indicators present in this dataflow.
_ASIA_DATA_TYPE_LABELS = {
    "LU": "unita_locali",       # number of local units of active enterprises
    "LUEMPDAA": "addetti",      # persons employed (annual average)
}
# How many years back to request (esploradati lags ~2-3y; we pick the latest
# TIME_PERIOD returned). lastNObservations triggers a server SQL error on this
# dataflow, so we bound with startPeriod instead.
_ASIA_YEARS_BACK = 6
_ASIA_BASE_DEFAULT = os.getenv("ISTAT_SDMX_BASE_URL", "https://esploradati.istat.it/SDMXWS/rest")
# Small per-comune result cache (the underlying get_csv is not cached).
_asia_cache: TTLCache = TTLCache(
    maxsize=int(os.getenv("ASIA_CACHE_MAXSIZE", "256")),
    ttl=int(os.getenv("ASIA_CACHE_TTL_SECONDS", "86400")),
)


def _sdmx_code(cell: str) -> str:
    """SDMX-CSV labels=both renders a dimension cell as 'CODE: Label'. Return CODE."""
    return cell.split(":", 1)[0].strip()


def _to_number(raw: str) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_asia_csv(text: str) -> dict[str, Any]:
    """Parse the single-comune ASIA SDMX-CSV.

    Returns a dict keyed by ATECO code → {"unita_locali": int, "addetti": float},
    plus the latest TIME_PERIOD found. Columns (labels=both):
      3=DATA_TYPE 4=ECON_ACTIVITY_NACE_2007 5=PERS_EMPL_SIZE_CLASS
      6=TIME_PERIOD 7=OBS_VALUE
    Only the TOTAL size class is kept, so per-ATECO values are never summed twice
    across employee-size brackets (defence-in-depth even if the key changes).
    """
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows or rows[0][:1] != ["DATAFLOW"]:
        return {"anno": None, "per_ateco": {}}
    body = rows[1:]
    years = {r[6] for r in body if len(r) > 6 and r[6]}
    if not years:
        return {"anno": None, "per_ateco": {}}
    latest = max(years)
    per_ateco: dict[str, dict[str, float]] = {}
    for r in body:
        if len(r) <= 7 or r[6] != latest:
            continue
        if _sdmx_code(r[5]) != _ASIA_TOTAL_SIZE:
            continue
        dt = _ASIA_DATA_TYPE_LABELS.get(_sdmx_code(r[3]))
        if dt is None:
            continue
        val = _to_number(r[7])
        if val is None:
            continue
        ateco = _sdmx_code(r[4])
        bucket = per_ateco.setdefault(ateco, {})
        bucket[dt] = int(val) if dt == "unita_locali" else round(val, 1)
    return {"anno": latest, "per_ateco": per_ateco}


async def fetch_imprese_comune(
    cod_comune: str,
    anno: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Fetch + aggregate the pinned ASIA dataflow for one comune.

    ONE SDMX-CSV call, key `A.{cod}...TOTAL`; returns totals + per-ATECO-section
    breakdown with the commerce section (G) highlighted, or `trovato=False` when the
    comune has no ASIA data. Results are cached per (base, comune, anno).
    """
    cod = (cod_comune or "").strip()
    base = (base_url or _ASIA_BASE_DEFAULT).rstrip("/")
    ck = (base, cod, anno or "latest")
    if ck in _asia_cache:
        return _asia_cache[ck]

    start = anno or str(datetime.now(timezone.utc).year - _ASIA_YEARS_BACK)
    # FREQ=A, REF_AREA=comune, DATA_TYPE/ATECO wild, SIZE=TOTAL (avoids
    # double-counting across employee-size classes).
    key = f"A.{cod}...{_ASIA_TOTAL_SIZE}"
    path = data_path(_ASIA_FLOW_ID, key)
    params: dict[str, Any] = {"startPeriod": start, "detail": "dataonly"}
    source_url = f"{base}/{path}?startPeriod={start}"

    async with SdmxClient(base_url=base) as c:
        csv_text = await c.get_csv(path, params=params)

    parsed = _parse_asia_csv(csv_text)
    per = parsed["per_ateco"]

    if not per:
        result = {
            "comune": cod,
            "trovato": False,
            "note": (
                f"Nessun dato ASIA (dataflow {_ASIA_FLOW_ID}) per il comune {cod}. "
                "Verifica il codice ISTAT a 6 cifre (CL_ITTER107)."
            ),
            "source_url": source_url,
        }
        _asia_cache[ck] = result
        return result

    def _bucket(ateco: str) -> dict[str, Any]:
        b = per.get(ateco, {})
        return {"unita_locali": b.get("unita_locali"), "addetti": b.get("addetti")}

    totale = _bucket(_ASIA_TOTAL_ATECO)
    commercio = _bucket(_ASIA_COMMERCIO_ATECO)
    tot_lu = totale.get("unita_locali")
    com_lu = commercio.get("unita_locali")
    if tot_lu and com_lu is not None:
        commercio["quota_unita_locali_pct"] = round(com_lu / tot_lu * 100, 1)
    commercio["ateco"] = _ASIA_COMMERCIO_ATECO

    per_sezione = {
        code: _bucket(code)
        for code in sorted(per)
        if len(code) == 1 and code.isalpha()
    }

    result = {
        "comune": cod,
        "anno": parsed["anno"],
        "totale": totale,
        "commercio": commercio,
        "per_sezione_ateco": per_sezione,
        "source_url": source_url,
        "sources": [
            {
                "url": source_url,
                "estratto_il": date.today().isoformat(),
                "licenza": "ISTAT — CC BY 4.0",
            }
        ],
        "trovato": True,
        "note": (
            f"ISTAT ASIA '{_ASIA_FLOW_ID}' (Unità locali e addetti), anno "
            f"{parsed['anno']}. unita_locali = imprese attive (sedi locali); "
            "addetti = media annua. Sezione G = commercio all'ingrosso e al dettaglio."
        ),
    }
    _asia_cache[ck] = result
    return result
