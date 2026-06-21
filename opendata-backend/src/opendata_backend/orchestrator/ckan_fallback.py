"""Deterministic CKAN search safety-net.

The LLM-driven CKAN specialist is the flaky link on a weak local model: it may
time out, emit malformed RESOURCES_JSON, or never call the search tool — so a
"trovami le piste ciclabili di Bologna" comes back empty even though the data is
on dati.gov.it (verified: count≈111, with GEOJSON/KML/SHP). This module runs a
direct CKAN `package_search` server-side and reuses the SAME deterministic
extraction (`_ckan_resources_from_payload`) and geographic post-filter
(`filter_resources`) as the aggregator, so real public datasets reach the user
regardless of the model. Used by the dataset-search entry points
(/datasets/search/stream and the A2A search/geo skills) as a fallback when the
agent surfaced nothing (or no geographic resource in map mode).
"""

from __future__ import annotations

import logging
import re

from opendata_core.ckan import CkanClient

from .geo_filter import filter_resources
from .parsing import Resource
from .synth import _ckan_resources_from_payload

log = logging.getLogger("orchestrator.ckan_fallback")

# Formats that can be drawn on the Leaflet map (mirrors lib/geoConvert.ts + the
# UI's zip/shapefile handling). ZIP is included: portals ship shapefiles zipped.
GEO_FORMATS = {
    "GEOJSON", "KML", "KMZ", "GPX", "SHP", "GPKG", "GML", "WMS", "WFS",
    "TOPOJSON", "ZIP",
}

# Strip command/connective words so the CKAN Solr query keeps real keywords
# ("trovami le piste ciclabili di Bologna" → "piste ciclabili bologna").
_STOPWORDS = {
    "trovami", "trova", "dammi", "mostrami", "cercami", "cerca", "voglio",
    "vorrei", "mi", "servono", "serve", "le", "la", "lo", "i", "gli", "il",
    "un", "una", "di", "del", "della", "dei", "degli", "delle", "a", "su",
    "per", "con", "e", "the", "find", "me", "show", "get", "dei",
}


def keywords(query: str) -> str:
    """Reduce a natural-language query to CKAN search keywords."""
    q = query
    if "USER QUERY:" in q:  # drop any MAP_MODE/PORTAL_HINT wrapper
        q = q.split("USER QUERY:", 1)[1]
    toks = re.findall(r"[\wàèéìòùÀÈÉÌÒÙ']+", q.lower())
    kept = [t for t in toks if t not in _STOPWORDS and len(t) > 1]
    return " ".join(kept) or query.strip()


def has_geo(resources: list[Resource]) -> bool:
    return any((r.format or "").upper() in GEO_FORMATS for r in resources)


async def ckan_geo_fallback(
    query: str,
    base_url: str | None,
    *,
    prefer_geo: bool,
    rows: int = 10,
) -> list[Resource]:
    """Run a deterministic CKAN package_search and return matching resources.

    Resources are passed through the SAME geographic post-filter as the
    aggregator (drops a different comune than the one named in the query). When
    `prefer_geo` and any geographic resource is found, non-geo ones are dropped.
    Returns [] on any failure — this is a best-effort safety net.
    """
    kw = keywords(query)
    if not kw:
        return []
    try:
        async with CkanClient() as client:
            result = await client.action(
                "package_search", base_url=base_url, params={"q": kw, "rows": rows}
            )
    except Exception as exc:  # network / CKAN error — never fatal
        log.warning("ckan_geo_fallback search failed for %r: %s", kw, exc)
        return []
    if not isinstance(result, dict):
        return []
    resources = _ckan_resources_from_payload(result)
    if not resources:
        return []
    resources = filter_resources(resources, query)
    if prefer_geo:
        geo = [r for r in resources if (r.format or "").upper() in GEO_FORMATS]
        if geo:
            resources = geo
    log.info(
        "ckan_geo_fallback: %r → %d resource(s) (kw=%r)", query[:60], len(resources), kw
    )
    return resources
