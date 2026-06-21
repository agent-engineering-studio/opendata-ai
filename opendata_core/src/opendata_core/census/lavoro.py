"""ISTAT 8milaCensus — indicatori del LAVORO a livello comunale (censimento 2011).

L'occupazione *residente* comunale non è disponibile via SDMX (esploradati e legacy
hanno solo dati sub-nazionali; i warehouse censimento sono dismessi). L'unica fonte
comunale è 8milaCensus, FERMA AL 2011: va sempre etichettata "Censimento 2011".

Struttura verificata live (2026-06): file per-regione
  https://ottomilacensus.istat.it/fileadmin/download/{RR}/confini/confini_{RR}.csv
encoding latin-1, separatore ';', più righe per comune (anni 1991/2001/2011 ai
confini 2011 → si filtra AnnoCP=2011). `Codice comune 2011` è senza zero iniziale
→ join con int(cod_comune). La regione {RR} si ricava dalla provincia
(int(cod)//1000) via `Province_Regioni_Italia_confini_2011.csv`.

Codici gruppo L (Lavoro) usati (dal codebook "Descrizione_degli_indicatori..."):
  L3 attività · L4 NEET 15-29 · L8 disoccupazione · L9 disoccupazione giovanile ·
  L12 occupazione · L14 occupazione 15-29 · L15-L18 settori · L19-L21 competenze.
"""

from __future__ import annotations

import csv
import io
import logging
import os
from datetime import date
from typing import Any

import httpx
from cachetools import TTLCache

log = logging.getLogger("opendata-core.census.lavoro")

_BASE_DEFAULT = os.getenv(
    "OTTOMILACENSUS_BASE_URL", "https://ottomilacensus.istat.it/fileadmin/download"
)
_USER_AGENT = os.getenv("OTTOMILACENSUS_USER_AGENT", "opendata-ai/1.0 (+territorial-analysis)")
_HTTP_TIMEOUT = float(os.getenv("OTTOMILACENSUS_HTTP_TIMEOUT", "60"))
_CENSUS_YEAR = "2011"

# Codice indicatore 8milaCensus → campo del nostro risultato.
_RATE_CODES = {
    "tasso_occupazione": "L12",
    "tasso_occupazione_giovanile": "L14",
    "tasso_disoccupazione": "L8",
    "tasso_disoccupazione_giovanile": "L9",
    "neet_15_29": "L4",
    "tasso_attivita": "L3",
}
_SETTORE_CODES = {
    "agricolo": "L15",
    "industriale": "L16",
    "terziario_extracommercio": "L17",
    "commercio": "L18",
}
_COMPETENZE_CODES = {
    "alta_media": "L19",
    "artigiane_operaie": "L20",
    "basse": "L21",
}

# 2011 = dato statico immutabile → cache lunga.
_TTL = int(os.getenv("OTTOMILACENSUS_CACHE_TTL_SECONDS", str(7 * 24 * 3600)))
_region_index_cache: TTLCache = TTLCache(maxsize=32, ttl=_TTL)  # regione → {comune_int: {Lcode: val}}
_result_cache: TTLCache = TTLCache(maxsize=512, ttl=_TTL)
_prov_region: dict[int, str] | None = None  # provincia(int) → regione "RR"


def _to_rate(raw: str) -> float | None:
    """Numero 8milaCensus → float. Decimali con virgola; '-' e '\\x85' = mancante."""
    s = (raw or "").strip()
    if not s or s in {"-", "\x85", "...", ".."}:
        return None
    try:
        return round(float(s.replace(".", "").replace(",", ".")), 1)
    except ValueError:
        return None


async def _get_text(client: httpx.AsyncClient, url: str) -> str:
    resp = await client.get(url)
    resp.raise_for_status()
    # i file 8milaCensus sono in latin-1 (Windows-1252)
    return resp.content.decode("latin-1")


async def _load_prov_region(client: httpx.AsyncClient, base: str) -> dict[int, str]:
    global _prov_region
    if _prov_region is not None:
        return _prov_region
    text = await _get_text(client, f"{base}/Province_Regioni_Italia_confini_2011.csv")
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    hdr = [h.strip() for h in rows[0]]
    i_anno, i_prov, i_reg = (
        hdr.index("AnnoCP"),
        hdr.index("Codice Provincia 2011"),
        hdr.index("Codice Regione 2011"),
    )
    mapping: dict[int, str] = {}
    for r in rows[1:]:
        if len(r) <= max(i_anno, i_prov, i_reg) or r[i_anno].strip() != _CENSUS_YEAR:
            continue
        prov, reg = r[i_prov].strip(), r[i_reg].strip()
        if prov and reg:
            mapping[int(prov)] = f"{int(reg):02d}"
    _prov_region = mapping
    return mapping


async def _load_region_index(
    client: httpx.AsyncClient, base: str, region: str
) -> dict[int, dict[str, str]]:
    if region in _region_index_cache:
        return _region_index_cache[region]
    text = await _get_text(client, f"{base}/{region}/confini/confini_{region}.csv")
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    hdr = [h.strip() for h in rows[0]]
    i_anno = hdr.index("AnnoCP")
    i_com = hdr.index("Codice comune 2011")
    # Tieni TUTTI i codici indicatore (P=popolazione, L=lavoro, …): l'indice è
    # condiviso tra le lenti census (lavoro legge i suoi L, welfare i suoi P).
    l_idx = {
        h: i for i, h in enumerate(hdr)
        if len(h) >= 2 and h[0].isalpha() and h[1:].isdigit()
    }
    index: dict[int, dict[str, str]] = {}
    for r in rows[1:]:
        if len(r) <= i_com or r[i_anno].strip() != _CENSUS_YEAR:
            continue
        com = r[i_com].strip()
        if not com.isdigit():
            continue
        index[int(com)] = {code: r[i] for code, i in l_idx.items() if i < len(r)}
    _region_index_cache[region] = index
    return index


async def fetch_lavoro_comune(cod_comune: str, base_url: str | None = None) -> dict[str, Any]:
    """Indicatori del lavoro (censimento 2011) di un comune da ISTAT 8milaCensus.

    Ritorna tasso di occupazione/disoccupazione (anche giovanile), NEET, attività,
    struttura settoriale e per competenze, con `source_url`/`sources`. Dato fermo al
    2011 (`anno`): è una fotografia STRUTTURALE, da etichettare "Censimento 2011".
    Comune assente → `trovato: false`. Cache per comune.
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

    def _vals(codes: dict[str, str]) -> dict[str, float | None]:
        return {field: _to_rate(row.get(code, "")) for field, code in codes.items()}

    rates = _vals(_RATE_CODES)
    result = {
        "comune": cod,
        "anno": _CENSUS_YEAR,
        **rates,
        "settori": _vals(_SETTORE_CODES),
        "competenze": _vals(_COMPETENZE_CODES),
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
            "ISTAT 8milaCensus, Censimento 2011 (dato strutturale, non congiunturale). "
            "Tassi % comunali: occupazione, disoccupazione (anche giovanile), NEET 15-29, "
            "attività; struttura per settore e per livello di competenza."
        ),
    }
    _result_cache[ck] = result
    return result
