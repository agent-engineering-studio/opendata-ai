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
    # Second tier — frequently appearing in open-data portals + EU metro areas
    "afragola", "altamura", "battipaglia", "bitonto", "casalnuovo",
    "casoria", "castellammare di stabia", "castellammare-di-stabia",
    "cava de tirreni", "cava-de-tirreni", "ercolano", "giugliano",
    "marano", "nocera inferiore", "nocera-inferiore", "pomigliano",
    "portici", "pozzuoli", "scafati", "sora", "torre del greco",
    "torre-del-greco", "torre annunziata", "torre-annunziata",
    "anzio", "civitavecchia", "fiumicino", "nettuno", "tivoli",
    "velletri", "viterbo", "albano", "ciampino", "marino", "pomezia",
    "altopascio", "empoli", "capannori", "viareggio", "scandicci",
    "san giovanni valdarno", "san-giovanni-valdarno",
    "abbiategrasso", "magenta", "saronno", "seregno", "vigevano",
    "voghera", "cernusco sul naviglio", "cernusco-sul-naviglio",
    "paderno dugnano", "paderno-dugnano", "san donato milanese",
    "san-donato-milanese", "san giuliano milanese", "san-giuliano-milanese",
    "settimo torinese", "settimo-torinese", "rivoli", "collegno",
    "nichelino", "grugliasco", "venaria", "venaria reale", "venaria-reale",
    "chivasso", "ivrea", "pinerolo", "alba", "bra",
    "chioggia", "mestre", "marghera", "mira", "spinea",
    "abano terme", "abano-terme", "albignasego", "cittadella",
    "este", "monselice", "piove di sacco", "piove-di-sacco",
    "san dona di piave", "san-dona-di-piave", "thiene",
    "valdagno", "arzignano", "bassano del grappa", "bassano-del-grappa",
    "conegliano", "vittorio veneto", "vittorio-veneto", "castelfranco veneto",
    "castelfranco-veneto", "mogliano veneto", "mogliano-veneto",
    "san dona", "san-dona", "jesolo", "caorle",
    "argenta", "comacchio", "lugo", "casalecchio di reno",
    "casalecchio-di-reno", "san lazzaro di savena", "san-lazzaro-di-savena",
    "castel maggiore", "castel-maggiore", "valsamoggia",
    "scandiano", "correggio", "sassuolo", "vignola",
    "fidenza", "salsomaggiore", "salsomaggiore terme", "salsomaggiore-terme",
)

# Sorted longest-first so multi-word names match before a substring like "san"
# or "reggio" would steal the match.
_COMUNI_SORTED = tuple(sorted(set(_KNOWN_COMUNI), key=len, reverse=True))


_TOKEN_SEP_RE = re.compile(r"[^a-z0-9]+")


def _normalise(text: str) -> str:
    """Lowercase + strip diacritics. Leave separators intact so the caller
    can tokenise consistently (any non-alphanumeric counts as a break)."""
    decomposed = unicodedata.normalize("NFKD", text)
    no_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return no_accents.lower()


def _find_comuni(text: str) -> set[str]:
    """Return the set of comuni named in `text`, normalised form.

    Strategy:
      1. Lowercase, strip diacritics, split on every non-alphanumeric
         character (handles `.`, `-`, `_`, `/`, `'`, spaces uniformly).
      2. Exact-token match for single-word comuni; contiguous-token-window
         match for multi-word comuni ("Reggio Emilia", "L'Aquila").
      3. URL escape hatch: when a token literally contains "comune" (e.g.
         the subdomain `opendatacomunegenova`), accept a city name as a
         substring of that token. This catches the real-world glued
         subdomain pattern without re-introducing the "como inside
         computazionale" false positive (no "comune" → no substring match).
    """
    if not text:
        return set()
    tokens = [t for t in _TOKEN_SEP_RE.split(_normalise(text)) if t]
    if not tokens:
        return set()

    found: set[str] = set()
    for comune in _COMUNI_SORTED:
        parts = comune.split()
        if len(parts) == 1:
            target = parts[0]
            for tok in tokens:
                if tok == target:
                    found.add(comune)
                    break
                if target in tok and ("comune" in tok or "comuni" in tok):
                    found.add(comune)
                    break
        else:
            n = len(parts)
            for i in range(len(tokens) - n + 1):
                if tokens[i : i + n] == parts:
                    found.add(comune)
                    break
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
