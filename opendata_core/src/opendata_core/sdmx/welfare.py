"""ISTAT DCIS_POPRES1 — comune-level welfare connector (struttura per età → indici).

La lente Welfare (Fase A) si ancora alla popolazione residente per età del comune:
da UNA sola call SDMX-CSV si ricavano gli indici demografici di fragilità sociale
(indice di vecchiaia, dipendenza anziani/strutturale, % over-65 / under-15) che
misurano il carico sui servizi socio-assistenziali. Stesso pattern di `asia.py`:
dataflow pinnato + key posizionale per singolo comune → chiamata piccola e
deterministica, iniettata server-side nell'aggregatore (l'LLM non inventa numeri).

Dataflow: 22_289_DF_DCIS_POPRES1_1 "Popolazione residente per età, sesso, comune"
(forma breve `22_289`, come ASIA usa `183_285`).

Key (6 dimensioni, TIME fuori dalla key) — VERIFICATA LIVE (esploradati IT1):
    FREQ.REF_AREA.DATA_TYPE.SEX.AGE.MARITAL_STATUS
→ popolazione al 1° gennaio, tutte le età, totale sesso/stato civile:
"A.{area}.JAN.9..99" (AGE vuota = tutte le classi). Colonne CSV: AGE / TIME_PERIOD
/ OBS_VALUE. Codici confermati: DATA_TYPE=JAN, SEX=9 (totale), MARITAL_STATUS=99.

NOTA: la variante `_1` copre Italia/regioni/province, NON i comuni (REF_AREA
comunale assente). Per il dato comunale va agganciata via env `POPRES_FLOW_ID` la
variante comunale di DCIS_POPRES1. Il parsing è per NOME COLONNA, non per
posizione: se un codice/area non esiste la query torna vuota → `trovato=False`
("dato insufficiente"), mai numeri falsi.
"""

from __future__ import annotations

import csv
import io
import os
import re
from datetime import date, datetime, timezone
from typing import Any

from cachetools import TTLCache

from .client import SdmxClient, data_path

# La forma corta "22_289" 404a: serve l'id pieno della variante. `_1` risolve
# (Italia/regioni/province); la variante comunale va impostata via env.
_POPRES_FLOW_ID = os.getenv("POPRES_FLOW_ID", "22_289_DF_DCIS_POPRES1_1")
# Codici CL_* VERIFICATI LIVE. DATA_TYPE "JAN" = popolazione al 1° gennaio;
# SEX 9 = totale; MARITAL_STATUS 99 = totale.
_POPRES_TIPO_DATO = os.getenv("POPRES_TIPO_DATO", "JAN")
_POPRES_SEX_TOTAL = os.getenv("POPRES_SEX_TOTAL", "9")
_POPRES_STATCIV_TOTAL = os.getenv("POPRES_STATCIV_TOTAL", "99")
# esploradati lagga ~2-3y; richiediamo qualche anno indietro e prendiamo il più recente.
_POPRES_YEARS_BACK = int(os.getenv("POPRES_YEARS_BACK", "4"))
_POPRES_BASE_DEFAULT = os.getenv("ISTAT_SDMX_BASE_URL", "https://esploradati.istat.it/SDMXWS/rest")

_cache: TTLCache = TTLCache(
    maxsize=int(os.getenv("POPRES_CACHE_MAXSIZE", "256")),
    ttl=int(os.getenv("POPRES_CACHE_TTL_SECONDS", "86400")),
)

# CL_ETA1: anni singoli "Y0".."Y100" + "Y_GE100" (100 e oltre) + "TOTAL".
# Sommiamo SOLO gli anni singoli (+ Y_GE100): le eventuali classi aggregate
# presenti nella codelist (es. "Y_GE65") vanno ignorate per non contare due volte
# le stesse persone — difesa in profondità anche se la key cambia.
_SINGLE_YEAR = re.compile(r"^Y(\d+)$")


def _sdmx_code(cell: str) -> str:
    """SDMX-CSV labels=both rende una cella dimensione come 'CODE: Label'. Ritorna CODE."""
    return cell.split(":", 1)[0].strip()


def _to_number(raw: str) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _age_of(code: str) -> int | None:
    """Età intera da un codice ETA1 (solo anni singoli 'Y<n>'), altrimenti None."""
    m = _SINGLE_YEAR.match(code)
    return int(m.group(1)) if m else None


def _parse_popres_csv(text: str) -> dict[str, Any]:
    """Parse della SDMX-CSV mono-comune di DCIS_POPRES1, per NOME colonna.

    Ritorna {"anno": latest, "per_eta": {codice_ETA1: valore}} per l'ultimo
    TIME_PERIOD disponibile. Il parsing localizza le colonne ETA1/TIME_PERIOD/
    OBS_VALUE dall'header (labels=both) invece di fissarne la posizione: robusto
    a colonne attributo extra e all'ordine esatto della DSD.
    """
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows or rows[0][:1] != ["DATAFLOW"]:
        return {"anno": None, "per_eta": {}}
    header = [h.strip() for h in rows[0]]

    def col(name: str) -> int | None:
        return header.index(name) if name in header else None

    # Colonna età = "AGE" (DSD reale), non "ETA1"; con fallback per robustezza.
    i_eta = col("AGE") if col("AGE") is not None else col("ETA1")
    i_time, i_obs = col("TIME_PERIOD"), col("OBS_VALUE")
    if i_eta is None or i_time is None or i_obs is None:
        return {"anno": None, "per_eta": {}}

    body = rows[1:]
    last = max(i_eta, i_time, i_obs)
    years = {r[i_time] for r in body if len(r) > i_time and r[i_time]}
    if not years:
        return {"anno": None, "per_eta": {}}
    latest = max(years)

    per_eta: dict[str, float] = {}
    for r in body:
        if len(r) <= last or r[i_time] != latest:
            continue
        val = _to_number(r[i_obs])
        if val is None:
            continue
        per_eta[_sdmx_code(r[i_eta])] = val
    return {"anno": latest, "per_eta": per_eta}


def _indici(per_eta: dict[str, float]) -> dict[str, Any] | None:
    """Calcola gli indici demografici dalle classi di età; None se dati insufficienti."""
    pop_0_14 = pop_15_64 = pop_65 = 0.0
    for code, val in per_eta.items():
        age = _age_of(code)
        if age is None:
            if code == "Y_GE100":  # 100 e oltre → over-65
                pop_65 += val
            continue  # TOTAL e classi aggregate: ignorate (no doppio conteggio)
        if age <= 14:
            pop_0_14 += val
        elif age <= 64:
            pop_15_64 += val
        else:
            pop_65 += val

    total = per_eta.get("TOTAL")
    if total is None:
        total = pop_0_14 + pop_15_64 + pop_65
    # Servono almeno la base 0-14 (denominatore indice di vecchiaia) e la
    # popolazione attiva; sotto questa soglia → "dato insufficiente".
    if pop_0_14 <= 0 or pop_15_64 <= 0 or total <= 0:
        return None

    def _r(x: float) -> float:
        return round(x, 1)

    return {
        "popolazione": int(total),
        "pop_0_14": int(pop_0_14),
        "pop_15_64": int(pop_15_64),
        "pop_65_piu": int(pop_65),
        "indice_vecchiaia": _r(pop_65 / pop_0_14 * 100),
        "indice_dipendenza_anziani": _r(pop_65 / pop_15_64 * 100),
        "indice_dipendenza_strutturale": _r((pop_0_14 + pop_65) / pop_15_64 * 100),
        "pct_over_65": _r(pop_65 / total * 100),
        "pct_under_15": _r(pop_0_14 / total * 100),
    }


async def fetch_welfare_comune(
    cod_comune: str,
    anno: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Indici demografici di fragilità del comune da ISTAT DCIS_POPRES1.

    UNA chiamata SDMX-CSV, key `A.{cod}.JAN..9.99`; ritorna gli indici + i conteggi
    per fascia, oppure `trovato=False` quando il comune non ha dati (codice ISTAT
    errato, dataflow vuoto, o codici CL_* da ricalibrare). Cache per (base, comune, anno).
    """
    cod = (cod_comune or "").strip()
    base = (base_url or _POPRES_BASE_DEFAULT).rstrip("/")
    ck = (base, cod, anno or "latest")
    if ck in _cache:
        return _cache[ck]

    start = anno or str(datetime.now(timezone.utc).year - _POPRES_YEARS_BACK)
    # Ordine reale: FREQ.REF_AREA.DATA_TYPE.SEX.AGE.MARITAL_STATUS → AGE vuota.
    key = f"A.{cod}.{_POPRES_TIPO_DATO}.{_POPRES_SEX_TOTAL}..{_POPRES_STATCIV_TOTAL}"
    path = data_path(_POPRES_FLOW_ID, key)
    params: dict[str, Any] = {"startPeriod": start, "detail": "dataonly"}
    source_url = f"{base}/{path}?startPeriod={start}"

    async with SdmxClient(base_url=base) as c:
        csv_text = await c.get_csv(path, params=params)

    parsed = _parse_popres_csv(csv_text)
    indici = _indici(parsed["per_eta"]) if parsed["per_eta"] else None

    if not indici:
        result = {
            "comune": cod,
            "trovato": False,
            "note": (
                f"Nessun dato popolazione (dataflow {_POPRES_FLOW_ID}) per il comune "
                f"{cod}. Verifica il codice ISTAT (CL_ITTER107) e i codici CL_* "
                "(TIPO_DATO15/SEXISTAT1/STATCIV2)."
            ),
            "source_url": source_url,
        }
        _cache[ck] = result
        return result

    result = {
        "comune": cod,
        "anno": parsed["anno"],
        **indici,
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
            f"ISTAT '{_POPRES_FLOW_ID}' (Popolazione residente), anno {parsed['anno']}. "
            "indice_vecchiaia = over-65 / under-15 ×100 (Italia ~190); "
            "indice_dipendenza_anziani = over-65 / pop 15-64 ×100. Misura il carico "
            "potenziale sui servizi socio-assistenziali per anziani."
        ),
    }
    _cache[ck] = result
    return result
