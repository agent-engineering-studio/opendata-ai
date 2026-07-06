"""ISTAT 8milaCensus — CONDIZIONI ABITATIVE della popolazione (censimento 2011).

Indicatori del patrimonio edilizio e delle condizioni abitative comunali: quota
di abitazioni in proprietà, abitazioni non occupate nei centri abitati, età
media del patrimonio recente, disponibilità dei servizi essenziali, superficie
per occupante, affollamento. Illumina le politiche abitative del comune.

Stessa fonte/meccanica delle lenti Lavoro e Istruzione: file per-regione
8milaCensus `confini_{RR}.csv` (latin-1, ';', riga AnnoCP=2011), indice
condiviso via gli helper di `lavoro.py`. Gruppo indicatori **A** (Condizioni
abitative ed insediamenti) dal codebook ufficiale
"Descrizione_degli_indicatori_serie_confini_2011.xlsx", verificato sul dato
reale (regione 16, Gioia del Colle 072021):
  A1 incidenza abitazioni in proprietà · A4 abitazioni non occupate nei centri
  abitati · A6 età media del patrimonio recente (costruzioni post-1962) · A7
  disponibilità dei servizi essenziali nell'abitazione · A12 mq per occupante ·
  A14 indice di affollamento delle abitazioni. Tutti già in % o unità dirette
  (Censimento 2011).
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

log = logging.getLogger("opendata-core.census.casa")

# Codice indicatore 8milaCensus (gruppo A) → campo del nostro risultato.
_A_CODES = {
    "incidenza_proprieta": "A1",
    "abitazioni_non_occupate_centri": "A4",
    "eta_media_patrimonio_recente": "A6",
    "disponibilita_servizi": "A7",
    "superficie_media_per_occupante": "A12",
    "affollamento_abitazioni": "A14",
}

_TTL = int(os.getenv("OTTOMILACENSUS_CACHE_TTL_SECONDS", str(7 * 24 * 3600)))
_result_cache: TTLCache = TTLCache(maxsize=512, ttl=_TTL)


async def fetch_casa_comune(cod_comune: str, base_url: str | None = None) -> dict[str, Any]:
    """Condizioni abitative (censimento 2011) di un comune da ISTAT 8milaCensus.

    Ritorna quota di abitazioni in proprietà, non occupate nei centri abitati,
    età media del patrimonio recente, disponibilità dei servizi essenziali,
    superficie per occupante e affollamento, con `source_url`/`sources`. Dato
    fermo al 2011 (`anno`): fotografia STRUTTURALE, da etichettare "Censimento
    2011". Comune assente o senza indici → `trovato: false` ("dato insufficiente").
    Cache per comune.
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
        field: _to_rate(row.get(code, "")) for field, code in _A_CODES.items()
    }
    # Sotto soglia: se nessun indicatore abitativo è valorizzato → dato insufficiente.
    if not any(v is not None for v in vals.values()):
        result = {
            "comune": cod,
            "trovato": False,
            "note": f"Nessun indicatore abitativo per il comune {cod} in 8milaCensus.",
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
            "ISTAT 8milaCensus, Censimento 2011 (dato strutturale). Condizioni abitative "
            "ed insediamenti (% comunali salvo dove indicato): abitazioni in proprietà, "
            "non occupate nei centri abitati, età media del patrimonio recente (anni), "
            "disponibilità dei servizi essenziali, superficie per occupante (mq), "
            "affollamento. Fotografa il patrimonio edilizio del territorio."
        ),
    }
    _result_cache[ck] = result
    return result
