"""Deterministic post-agent geographic filter.

The CKAN_INSTRUCTIONS system prompt tells the model to drop search results that
don't mention the queried place. In practice the model often returns a national
or multi-comune dataset whose record passes the "title contains Bologna" check
but whose resource URLs point at a different city — e.g. asking for "piste
ciclabili Bologna" surfaces an `opendatacomunegenova.s3…` zip alongside the
genuine Bologna data.

This module runs a deterministic pass after the aggregator has merged all
agents' resources: if the user query names one or more Italian comuni, every
resource whose URL/name names a *different* comune (and not one from the
query) is dropped. Resources without any recognised comune in the URL are
kept (national / regional / aggregate datasets are still valid for a city
query).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Iterable

from .parsing import Resource

log = logging.getLogger("orchestrator.geo_filter")

# Italian capoluoghi di provincia + a handful of major non-capoluogo cities that
# commonly publish open data. Lowercase, with diacritics stripped, in the form
# typically used inside URLs and slugs (multi-word names use both spellings).
# Extend as the catalogue surfaces new cities.
_KNOWN_COMUNI: tuple[str, ...] = (
    # Major metropolitan
    "roma", "milano", "napoli", "torino", "palermo", "genova", "bologna",
    "firenze", "bari", "catania", "venezia", "verona", "messina", "padova",
    "trieste", "brescia", "taranto", "prato", "parma", "reggio emilia",
    "reggio-emilia", "modena", "reggio calabria", "reggio-calabria",
    # Capoluoghi di regione + provincia
    "ancona", "aosta", "campobasso", "cagliari", "catanzaro", "perugia",
    "potenza", "trento", "bolzano", "udine", "pordenone", "gorizia",
    "belluno", "rovigo", "vicenza", "treviso", "bergamo", "como", "varese",
    "lecco", "lodi", "monza", "mantova", "cremona", "pavia", "sondrio",
    "novara", "alessandria", "asti", "biella", "cuneo", "vercelli",
    "verbania", "verbano-cusio-ossola", "savona", "imperia", "la spezia",
    "la-spezia", "piacenza", "ferrara", "ravenna", "forli", "forli-cesena",
    "rimini", "pistoia", "arezzo", "siena", "grosseto", "livorno", "lucca",
    "pisa", "massa", "massa-carrara", "carrara", "viterbo", "rieti",
    "frosinone", "latina", "terni", "ascoli piceno", "ascoli-piceno",
    "fermo", "macerata", "pesaro", "urbino", "pesaro-urbino", "teramo",
    "pescara", "chieti", "l aquila", "laquila", "l-aquila", "isernia",
    "matera", "cosenza", "crotone", "vibo valentia", "vibo-valentia",
    "trapani", "agrigento", "caltanissetta", "enna", "ragusa", "siracusa",
    "sassari", "nuoro", "oristano", "olbia", "olbia-tempio", "carbonia",
    "iglesias", "lecce", "brindisi", "foggia", "barletta", "andria",
    "trani", "salerno", "avellino", "benevento", "caserta",
    # Other commonly-publishing comuni
    "alghero", "andria", "asti", "barletta", "benevento", "bisceglie",
    "busto arsizio", "busto-arsizio", "carpi", "cesena", "cinisello balsamo",
    "fano", "faenza", "guidonia", "imola", "legnano", "marsala",
    "molfetta", "monopoli", "moncalieri", "pesaro", "rho", "rozzano",
    "san remo", "san-remo", "sanremo", "schio", "sesto san giovanni",
    "sesto-san-giovanni", "trapani",
)

# Sorted longest-first so multi-word names match before a substring like "san"
# or "reggio" would steal the match.
_COMUNI_SORTED = tuple(sorted(set(_KNOWN_COMUNI), key=len, reverse=True))


def _normalise(text: str) -> str:
    """Lowercase + strip diacritics + collapse separators to spaces."""
    decomposed = unicodedata.normalize("NFKD", text)
    no_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    # Replace common URL/slug separators with space so "reggio-emilia" and
    # "reggio_emilia" and "reggio emilia" all match the same token form.
    return re.sub(r"[._/\-+]+", " ", no_accents.lower())


def _find_comuni(text: str) -> set[str]:
    """Return the set of comuni found in `text`, normalised form.

    Matches are word-boundary-aware so a comune doesn't accidentally match a
    substring of an unrelated word (e.g. "como" inside "computazionale").
    """
    if not text:
        return set()
    norm = _normalise(text)
    found: set[str] = set()
    for comune in _COMUNI_SORTED:
        # \b is ASCII-only here, which is fine: _normalise has already stripped
        # diacritics and lowercased.
        if re.search(rf"\b{re.escape(comune)}\b", norm):
            found.add(comune)
    return found


def extract_places(query: str) -> set[str]:
    """Comuni named in the user's query, normalised."""
    return _find_comuni(query)


def filter_resources(
    resources: Iterable[Resource], query: str
) -> list[Resource]:
    """Drop resources whose URL/name names a different comune than the query.

    Decision per resource:
      - query mentions no comune → keep all (no scoping signal to apply).
      - resource URL+name mention no comune → keep (national/regional/aggregate
        catalogue, still potentially relevant).
      - resource mentions at least one comune that is also in the query → keep.
      - resource mentions only comuni that are NOT in the query → drop.
    """
    resources = list(resources)
    wanted = extract_places(query)
    if not wanted:
        return resources

    kept: list[Resource] = []
    dropped: list[tuple[str, set[str]]] = []
    for r in resources:
        haystack = f"{r.url} {r.name or ''}"
        present = _find_comuni(haystack)
        if not present:
            kept.append(r)
            continue
        if present & wanted:
            kept.append(r)
            continue
        dropped.append((r.url, present))

    if dropped:
        log.info(
            "geo_filter: query=%s kept=%d dropped=%d (off-place samples=%s)",
            sorted(wanted),
            len(kept),
            len(dropped),
            [f"{url[:80]}…→{sorted(places)}" for url, places in dropped[:3]],
        )
    return kept
