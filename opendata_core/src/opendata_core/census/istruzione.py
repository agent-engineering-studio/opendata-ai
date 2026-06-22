"""ISTAT 8milaCensus — GRADO DI ISTRUZIONE della popolazione (censimento 2011).

Indicatori del livello di istruzione *della popolazione residente* (esiti, non
offerta scolastica): % laureati, % con diploma o laurea, % con sola licenza media,
tasso di analfabetismo, uscita precoce dal sistema di istruzione. Complementare ai
conteggi MIUR (scuole/alunni = offerta) nella lente Istruzione.

Stessa fonte/meccanica della lente Lavoro: file per-regione 8milaCensus
`confini_{RR}.csv` (latin-1, ';', riga AnnoCP=2011), indice condiviso via gli helper
di `lavoro.py`. Gruppo indicatori **I** (Istruzione) dal codebook ufficiale
"Descrizione_degli_indicatori_serie_confini_2011.xlsx":
  I2 adulti in apprendimento permanente · I4 incidenza analfabeti · I5 uscita
  precoce 15-24 · I6 adulti 25-64 con diploma o laurea · I7 giovani 30-34 con
  laurea · I9 adulti 25-64 con sola licenza media. Tutti già in % (Censimento 2011).
"""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any

import httpx
from cachetools import TTLCache

from .lavoro import (
    _BASE_DEFAULT,
    _CENSUS_YEAR,
    _HTTP_TIMEOUT,
    _USER_AGENT,
    _load_prov_region,
    _load_region_index,
    _to_rate,
)

log = logging.getLogger("opendata-core.census.istruzione")

# Codice indicatore 8milaCensus (gruppo I) → campo del nostro risultato. Tutti %.
_I_CODES = {
    "incidenza_laureati_30_34": "I7",
    "incidenza_diploma_o_laurea_25_64": "I6",
    "incidenza_licenza_media_25_64": "I9",
    "incidenza_analfabeti": "I4",
    "uscita_precoce_15_24": "I5",
    "adulti_apprendimento_permanente": "I2",
}

_TTL = int(os.getenv("OTTOMILACENSUS_CACHE_TTL_SECONDS", str(7 * 24 * 3600)))
_result_cache: TTLCache = TTLCache(maxsize=512, ttl=_TTL)


async def fetch_grado_istruzione_comune(
    cod_comune: str, base_url: str | None = None
) -> dict[str, Any]:
    """Grado di istruzione della popolazione (censimento 2011) di un comune da 8milaCensus.

    Ritorna le quote % per titolo di studio (laureati 30-34, diploma+laurea 25-64,
    sola licenza media, analfabeti, uscita precoce) con `source_url`/`sources`. Dato
    fermo al 2011 (`anno`): fotografia STRUTTURALE, da etichettare "Censimento 2011".
    Comune assente o senza indici → `trovato: false` ("dato insufficiente"). Cache per comune.
    """
    cod = (cod_comune or "").strip()
    base = (base_url or _BASE_DEFAULT).rstrip("/")
    ck = (base, cod)
    if ck in _result_cache:
        return _result_cache[ck]

    try:
        com_int = int(cod)
    except ValueError:
        return {"comune": cod, "trovato": False, "note": "Codice comune non numerico."}
    prov = com_int // 1000

    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT, headers={"User-Agent": _USER_AGENT}, follow_redirects=True
    ) as client:
        prov_region = await _load_prov_region(client, base)
        region = prov_region.get(prov)
        if region is None:
            result = {
                "comune": cod,
                "trovato": False,
                "note": f"Provincia {prov} non mappata a una regione 8milaCensus.",
            }
            _result_cache[ck] = result
            return result
        index = await _load_region_index(client, base, region)

    row = index.get(com_int)
    source_url = f"{base}/{region}/confini/confini_{region}.csv"
    if not row:
        result = {
            "comune": cod,
            "trovato": False,
            "note": f"Comune {cod} assente in 8milaCensus (confini 2011, regione {region}).",
            "source_url": source_url,
        }
        _result_cache[ck] = result
        return result

    vals: dict[str, float | None] = {
        field: _to_rate(row.get(code, "")) for field, code in _I_CODES.items()
    }
    # Sotto soglia: se nessun indicatore istruzione è valorizzato → dato insufficiente.
    if not any(v is not None for v in vals.values()):
        result = {
            "comune": cod,
            "trovato": False,
            "note": f"Nessun indicatore di istruzione per il comune {cod} in 8milaCensus.",
            "source_url": source_url,
        }
        _result_cache[ck] = result
        return result

    result = {
        "comune": cod,
        "anno": _CENSUS_YEAR,
        **vals,
        "source_url": source_url,
        "sources": [
            {
                "url": source_url,
                "estratto_il": date.today().isoformat(),
                "licenza": "ISTAT 8milaCensus — CC BY 4.0",
            }
        ],
        "trovato": True,
        "note": (
            "ISTAT 8milaCensus, Censimento 2011 (dato strutturale). Grado di istruzione "
            "della POPOLAZIONE residente (% comunali): laureati 30-34, diploma o laurea "
            "25-64, sola licenza media 25-64, analfabeti, uscita precoce 15-24. Misura "
            "gli esiti formativi del territorio (capitale umano), distinti dall'offerta scolastica."
        ),
    }
    _result_cache[ck] = result
    return result
