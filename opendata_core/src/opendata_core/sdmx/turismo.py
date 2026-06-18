"""ISTAT — capacità degli esercizi ricettivi a livello comunale (lente Turismo).

Ancora ISTAT (affidabile, cache-ata) per la lente Turismo/Cultura: posti letto +
numero esercizi del comune. Complementa l'ancora OSM (asset culturali) misurando
la capacità di accoglienza — quanto il territorio capitalizza il suo patrimonio.

Struttura verificata live (2026-06): dataflow 122_54 / DSD DCSC_TUR "Capacity of
collective accommodation establishments and Occupancy...". 11 dimensioni; per la
sola CAPACITÀ totale del comune si fissano TYPE_ACCOMMODATION=ALL e SIZE=TOT.

Key order:
  FREQ.REF_AREA.DATA_TYPE.ADJUSTMENT.TYPE_ACCOMMODATION.ECON_ACTIVITY_NACE_2007.
  COUNTRY_RES_GUESTS.LOCALITY_TYPE.URBANIZ_DEGREE.COASTAL_AREA.SIZE_BY_NUMBER_ROOMS
→ singolo comune, totale ricettività: "A.{cod}...ALL......TOT".
"""

from __future__ import annotations

import csv
import io
import os
from datetime import date, datetime, timezone
from typing import Any

from cachetools import TTLCache

from .asia import _sdmx_code, _to_number
from .client import SdmxClient, data_path

_TUR_FLOW_ID = os.getenv("TURISMO_FLOW_ID", "122_54")
# CL_TIPO_DATO7 (DATA_TYPE): indicatori di capacità → nostri campi.
_TUR_DATA_TYPE_LABELS = {
    "BEDS": "posti_letto",       # bed-places
    "NUM_EST": "esercizi",       # number of establishments
    "BED_RMS": "camere",         # bedrooms
}
_TUR_YEARS_BACK = 3
_TUR_BASE_DEFAULT = os.getenv("ISTAT_SDMX_BASE_URL", "https://esploradati.istat.it/SDMXWS/rest")
# Chiave: FREQ=A, REF_AREA=comune, TYPE_ACCOMMODATION=ALL (totale strutture),
# SIZE_BY_NUMBER_ROOMS=TOT (totale classi); resto wild.
_TUR_KEY_TEMPLATE = ("A", "{cod}", "", "", "ALL", "", "", "", "", "", "TOT")

_tur_cache: TTLCache = TTLCache(
    maxsize=int(os.getenv("TURISMO_CACHE_MAXSIZE", "256")),
    ttl=int(os.getenv("TURISMO_CACHE_TTL_SECONDS", "86400")),
)


def _parse_ricettivita_csv(text: str) -> dict[str, Any]:
    """Parse il CSV ricettività (TYPE_ACCOMMODATION/SIZE già fissati a ALL/TOT).

    Colonne (labels=both): 3=DATA_TYPE 12=TIME_PERIOD 13=OBS_VALUE. Ritorna
    `{anno, valori: {posti_letto, esercizi, camere}}` per l'ultimo anno presente.
    """
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or rows[0][:1] != ["DATAFLOW"]:
        return {"anno": None, "valori": {}}
    body = rows[1:]
    years = {r[12] for r in body if len(r) > 12 and r[12]}
    if not years:
        return {"anno": None, "valori": {}}
    latest = max(years)
    valori: dict[str, int] = {}
    for r in body:
        if len(r) <= 13 or r[12] != latest:
            continue
        field = _TUR_DATA_TYPE_LABELS.get(_sdmx_code(r[3]))
        if field is None:
            continue
        val = _to_number(r[13])
        if val is not None:
            valori[field] = int(val)
    return {"anno": latest, "valori": valori}


async def fetch_ricettivita_comune(
    cod_comune: str,
    anno: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Posti letto + esercizi ricettivi di un comune da ISTAT (dataflow 122_54).

    UNA call SDMX-CSV con chiave fissata su ALL/TOT (totale strutture e classi).
    Ritorna l'ultimo anno disponibile, o `trovato=False` se il comune non ha dati
    di capacità ricettiva. Cache per (base, comune, anno).
    """
    cod = (cod_comune or "").strip()
    base = (base_url or _TUR_BASE_DEFAULT).rstrip("/")
    ck = (base, cod, anno or "latest")
    if ck in _tur_cache:
        return _tur_cache[ck]

    start = anno or str(datetime.now(timezone.utc).year - _TUR_YEARS_BACK)
    key = ".".join(p.format(cod=cod) for p in _TUR_KEY_TEMPLATE)
    path = data_path(_TUR_FLOW_ID, key)
    params: dict[str, Any] = {"startPeriod": start, "detail": "dataonly"}
    source_url = f"{base}/{path}?startPeriod={start}"

    async with SdmxClient(base_url=base) as c:
        csv_text = await c.get_csv(path, params=params)

    parsed = _parse_ricettivita_csv(csv_text)
    valori = parsed["valori"]
    if not valori:
        result = {
            "comune": cod,
            "trovato": False,
            "note": (
                f"Nessun dato di capacità ricettiva ISTAT (dataflow {_TUR_FLOW_ID}) "
                f"per il comune {cod}."
            ),
            "source_url": source_url,
        }
        _tur_cache[ck] = result
        return result

    result = {
        "comune": cod,
        "anno": parsed["anno"],
        "posti_letto": valori.get("posti_letto"),
        "esercizi": valori.get("esercizi"),
        "camere": valori.get("camere"),
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
            f"ISTAT '{_TUR_FLOW_ID}' (Capacità esercizi ricettivi), anno "
            f"{parsed['anno']}: posti letto e numero esercizi (totale strutture). "
            "Incrocia con popolazione e asset culturali per valutare la capacità di "
            "accoglienza vs il potenziale turistico."
        ),
    }
    _tur_cache[ck] = result
    return result
