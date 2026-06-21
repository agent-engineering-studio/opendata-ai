"""ISTAT 8milaCensus — indici demografici / WELFARE a livello COMUNALE (censimento 2011).

Stessa fonte e stesso file di `census.lavoro` (confini_{RR}.csv): da UNA riga
comunale si ricavano gli indici di struttura demografica che misurano il carico
sui servizi socio-assistenziali (indice di vecchiaia, dipendenza anziani/giovanile/
strutturale, % grandi anziani 75+, …). È l'ANCORA COMUNALE del welfare: a differenza
del SDMX DCIS_POPRES1 (solo Italia/regioni/province), 8milaCensus copre tutti i
comuni. Dato STRUTTURALE fermo al 2011 → va etichettato "Censimento 2011".

Codici gruppo P (Popolazione) dal codebook ufficiale
"Descrizione_degli_indicatori_serie_confini_2011" (verificato live, 2026-06):
  P1  popolazione residente (valore assoluto)
  P7  densità (ab./kmq)
  P8  rapporto di mascolinità (M/F ×100)
  P9  % popolazione < 6 anni
  P10 % popolazione 75 anni e più
  P11 indice di dipendenza degli anziani (65+ / 15-64 ×100)
  P12 indice di dipendenza giovanile (0-14 / 15-64 ×100)
  P13 indice di vecchiaia (65+ / 0-14 ×100)
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

log = logging.getLogger("opendata-core.census.welfare")

# Codice indicatore 8milaCensus (gruppo P) → campo del nostro risultato.
_P_CODES = {
    "popolazione": "P1",
    "densita_ab_kmq": "P7",
    "rapporto_mascolinita": "P8",
    "pct_under_6": "P9",
    "pct_over_75": "P10",
    "indice_dipendenza_anziani": "P11",
    "indice_dipendenza_giovanile": "P12",
    "indice_vecchiaia": "P13",
}

_TTL = int(os.getenv("OTTOMILACENSUS_CACHE_TTL_SECONDS", str(7 * 24 * 3600)))
_result_cache: TTLCache = TTLCache(maxsize=512, ttl=_TTL)


async def fetch_welfare_comune(cod_comune: str, base_url: str | None = None) -> dict[str, Any]:
    """Indici demografici di fragilità (censimento 2011) di un comune da 8milaCensus.

    Ritorna indice di vecchiaia, dipendenza anziani/giovanile/strutturale, % 75+,
    % <6, densità e rapporto di mascolinità, con `source_url`/`sources`. Dato fermo
    al 2011 (`anno`): fotografia STRUTTURALE, da etichettare "Censimento 2011".
    Comune assente o senza indici → `trovato: false` ("dato insufficiente", mai
    numeri falsi). Cache per comune.
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
        field: _to_rate(row.get(code, "")) for field, code in _P_CODES.items()
    }
    # La popolazione è un conteggio, non un tasso → intero.
    if vals.get("popolazione") is not None:
        vals["popolazione"] = int(vals["popolazione"])

    iv = vals.get("indice_vecchiaia")
    da = vals.get("indice_dipendenza_anziani")
    dg = vals.get("indice_dipendenza_giovanile")
    # Serve almeno l'indice di vecchiaia o la dipendenza anziani per dire qualcosa.
    if iv is None and da is None:
        result = {
            "comune": cod,
            "trovato": False,
            "note": "Indici demografici 8milaCensus non disponibili per il comune.",
            "source_url": source_url,
        }
        _result_cache[ck] = result
        return result

    indice_dipendenza_strutturale = (
        round(da + dg, 1) if (da is not None and dg is not None) else None
    )

    result = {
        "comune": cod,
        "anno": _CENSUS_YEAR,
        **vals,
        "indice_dipendenza_strutturale": indice_dipendenza_strutturale,
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
            "ISTAT 8milaCensus, Censimento 2011 (dato strutturale comunale, non "
            "congiunturale). indice_vecchiaia = over-65 / under-15 ×100 (Italia 2011 "
            "~148); indice_dipendenza_anziani = over-65 / pop 15-64 ×100. Misurano il "
            "carico potenziale sui servizi socio-assistenziali per anziani."
        ),
    }
    _result_cache[ck] = result
    return result
