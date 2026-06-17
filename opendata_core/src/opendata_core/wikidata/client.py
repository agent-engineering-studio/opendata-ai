"""Wikidata SPARQL: arricchimento di un comune via codice ISTAT (P635). Dati: CC0.

Best-effort: l'endpoint pubblico throttla e il formato del codice può variare;
su qualsiasi errore/zero match ritorna None.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

WIKIDATA_LICENSE = "CC0 (wikidata.org)"
SPARQL_URL = os.getenv("WIKIDATA_SPARQL_URL", "https://query.wikidata.org/sparql")
HTTP_TIMEOUT = float(os.getenv("WIKIDATA_TIMEOUT", "20"))
_USER_AGENT = "opendata-ai/0.1 (+https://github.com/agent-engineering-studio)"

# P635 = codice ISTAT del comune; P1082 popolazione; P2046 superficie; P856 sito web.
_QUERY = """
SELECT ?item ?itemLabel ?population ?area ?website WHERE {{
  ?item wdt:P635 "{istat}" .
  OPTIONAL {{ ?item wdt:P1082 ?population. }}
  OPTIONAL {{ ?item wdt:P2046 ?area. }}
  OPTIONAL {{ ?item wdt:P856 ?website. }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "it,en". }}
}} LIMIT 1
"""


class WikidataError(RuntimeError):
    """Wikidata non raggiungibile o risposta inattesa."""


def _first(bindings: list[dict[str, Any]], key: str) -> str | None:
    for b in bindings:
        if key in b and b[key].get("value"):
            return b[key]["value"]
    return None


async def comune_by_istat(istat_code: str) -> dict[str, Any] | None:
    """Arricchimento Wikidata per codice ISTAT. None se nessun match o errore."""
    query = _QUERY.format(istat=istat_code.strip())
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            r = await client.get(
                SPARQL_URL,
                params={"query": query, "format": "json"},
                headers={"User-Agent": _USER_AGENT, "Accept": "application/sparql-results+json"},
            )
            r.raise_for_status()
            data = r.json()
    except (httpx.HTTPError, ValueError):
        return None

    bindings = (data.get("results") or {}).get("bindings") or []
    if not bindings:
        return None
    qid_url = _first(bindings, "item")
    pop = _first(bindings, "population")
    area = _first(bindings, "area")
    return {
        "qid": qid_url.rsplit("/", 1)[-1] if qid_url else None,
        "label": _first(bindings, "itemLabel"),
        "population": int(float(pop)) if pop else None,
        "area_km2": float(area) if area else None,
        "website": _first(bindings, "website"),
        "license": WIKIDATA_LICENSE,
    }
