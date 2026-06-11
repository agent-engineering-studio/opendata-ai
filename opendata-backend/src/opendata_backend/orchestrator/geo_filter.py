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


# ── Regioni italiane ─────────────────────────────────────────────────────
# Both spaced and glued forms are recognised: regional portals love to
# concatenate the name in the domain (`dati.friuliveneziagiulia.it`,
# `dati.emilia-romagna.it`, `siciliaregione.it`). Glued tokens survive
# tokenisation as a single token, so we list them explicitly and exact-match
# them as if they were single-word comuni.
_KNOWN_REGIONS: tuple[str, ...] = (
    "abruzzo", "basilicata", "calabria", "campania",
    "emilia romagna", "emilia-romagna", "emiliaromagna",
    "friuli venezia giulia", "friuli-venezia-giulia", "friuliveneziagiulia",
    "lazio", "liguria", "lombardia", "marche", "molise",
    "piemonte", "puglia", "sardegna", "sicilia", "siciliaregione",
    "toscana", "trentino alto adige", "trentino-alto-adige", "trentinoaltoadige",
    "umbria", "valle d aosta", "valle-d-aosta", "valledaosta", "veneto",
)
_REGIONS_SORTED = tuple(sorted(set(_KNOWN_REGIONS), key=len, reverse=True))

# Canonical region label (one per region, used in the comune→region map and in
# log output). The matcher accepts all the spelling variants above but
# normalises them to the canonical form below before set comparison.
_REGION_CANONICAL: dict[str, str] = {
    "emilia romagna": "emilia-romagna",
    "emilia-romagna": "emilia-romagna",
    "emiliaromagna": "emilia-romagna",
    "friuli venezia giulia": "friuli-venezia-giulia",
    "friuli-venezia-giulia": "friuli-venezia-giulia",
    "friuliveneziagiulia": "friuli-venezia-giulia",
    "trentino alto adige": "trentino-alto-adige",
    "trentino-alto-adige": "trentino-alto-adige",
    "trentinoaltoadige": "trentino-alto-adige",
    "valle d aosta": "valle-d-aosta",
    "valle-d-aosta": "valle-d-aosta",
    "valledaosta": "valle-d-aosta",
    "siciliaregione": "sicilia",
}


# Map comune (normalised, matches a key in _COMUNI_SORTED) → canonical region.
# Only comuni in _KNOWN_COMUNI need an entry; missing entries simply skip the
# region scope check. Extend as the whitelist grows.
_COMUNE_TO_REGION: dict[str, str] = {
    # Lazio
    "roma": "lazio", "viterbo": "lazio", "rieti": "lazio", "frosinone": "lazio",
    "latina": "lazio", "anzio": "lazio", "civitavecchia": "lazio",
    "fiumicino": "lazio", "nettuno": "lazio", "tivoli": "lazio",
    "velletri": "lazio", "albano": "lazio", "ciampino": "lazio",
    "marino": "lazio", "pomezia": "lazio",
    # Lombardia
    "milano": "lombardia", "brescia": "lombardia", "bergamo": "lombardia",
    "como": "lombardia", "varese": "lombardia", "lecco": "lombardia",
    "lodi": "lombardia", "monza": "lombardia", "mantova": "lombardia",
    "cremona": "lombardia", "pavia": "lombardia", "sondrio": "lombardia",
    "busto arsizio": "lombardia", "busto-arsizio": "lombardia",
    "cinisello balsamo": "lombardia", "legnano": "lombardia",
    "rho": "lombardia", "rozzano": "lombardia",
    "sesto san giovanni": "lombardia", "sesto-san-giovanni": "lombardia",
    "abbiategrasso": "lombardia", "magenta": "lombardia",
    "saronno": "lombardia", "seregno": "lombardia", "vigevano": "lombardia",
    "voghera": "lombardia",
    "cernusco sul naviglio": "lombardia", "cernusco-sul-naviglio": "lombardia",
    "paderno dugnano": "lombardia", "paderno-dugnano": "lombardia",
    "san donato milanese": "lombardia", "san-donato-milanese": "lombardia",
    "san giuliano milanese": "lombardia",
    "san-giuliano-milanese": "lombardia",
    # Campania
    "napoli": "campania", "salerno": "campania", "avellino": "campania",
    "benevento": "campania", "caserta": "campania", "afragola": "campania",
    "battipaglia": "campania", "casalnuovo": "campania", "casoria": "campania",
    "castellammare di stabia": "campania",
    "castellammare-di-stabia": "campania",
    "cava de tirreni": "campania", "cava-de-tirreni": "campania",
    "ercolano": "campania", "giugliano": "campania", "marano": "campania",
    "nocera inferiore": "campania", "nocera-inferiore": "campania",
    "pomigliano": "campania", "portici": "campania", "pozzuoli": "campania",
    "scafati": "campania", "torre del greco": "campania",
    "torre-del-greco": "campania", "torre annunziata": "campania",
    "torre-annunziata": "campania",
    # Piemonte
    "torino": "piemonte", "novara": "piemonte", "alessandria": "piemonte",
    "asti": "piemonte", "biella": "piemonte", "cuneo": "piemonte",
    "vercelli": "piemonte", "verbania": "piemonte",
    "verbano-cusio-ossola": "piemonte",
    "moncalieri": "piemonte", "settimo torinese": "piemonte",
    "settimo-torinese": "piemonte", "rivoli": "piemonte",
    "collegno": "piemonte", "nichelino": "piemonte", "grugliasco": "piemonte",
    "venaria": "piemonte", "venaria reale": "piemonte",
    "venaria-reale": "piemonte", "chivasso": "piemonte",
    "ivrea": "piemonte", "pinerolo": "piemonte", "alba": "piemonte",
    "bra": "piemonte",
    # Sicilia
    "palermo": "sicilia", "catania": "sicilia", "messina": "sicilia",
    "trapani": "sicilia", "agrigento": "sicilia",
    "caltanissetta": "sicilia", "enna": "sicilia", "ragusa": "sicilia",
    "siracusa": "sicilia", "marsala": "sicilia",
    # Liguria
    "genova": "liguria", "savona": "liguria", "imperia": "liguria",
    "la spezia": "liguria", "la-spezia": "liguria",
    "san remo": "liguria", "san-remo": "liguria", "sanremo": "liguria",
    # Emilia-Romagna
    "bologna": "emilia-romagna", "parma": "emilia-romagna",
    "reggio emilia": "emilia-romagna", "reggio-emilia": "emilia-romagna",
    "modena": "emilia-romagna", "piacenza": "emilia-romagna",
    "ferrara": "emilia-romagna", "ravenna": "emilia-romagna",
    "forli": "emilia-romagna", "forli-cesena": "emilia-romagna",
    "rimini": "emilia-romagna", "cesena": "emilia-romagna",
    "carpi": "emilia-romagna", "faenza": "emilia-romagna",
    "imola": "emilia-romagna", "argenta": "emilia-romagna",
    "comacchio": "emilia-romagna", "lugo": "emilia-romagna",
    "casalecchio di reno": "emilia-romagna",
    "casalecchio-di-reno": "emilia-romagna",
    "san lazzaro di savena": "emilia-romagna",
    "san-lazzaro-di-savena": "emilia-romagna",
    "castel maggiore": "emilia-romagna", "castel-maggiore": "emilia-romagna",
    "valsamoggia": "emilia-romagna", "scandiano": "emilia-romagna",
    "correggio": "emilia-romagna", "sassuolo": "emilia-romagna",
    "vignola": "emilia-romagna", "fidenza": "emilia-romagna",
    "salsomaggiore": "emilia-romagna",
    "salsomaggiore terme": "emilia-romagna",
    "salsomaggiore-terme": "emilia-romagna",
    # Toscana
    "firenze": "toscana", "prato": "toscana", "pistoia": "toscana",
    "arezzo": "toscana", "siena": "toscana", "grosseto": "toscana",
    "livorno": "toscana", "lucca": "toscana", "pisa": "toscana",
    "massa": "toscana", "massa-carrara": "toscana", "carrara": "toscana",
    "altopascio": "toscana", "empoli": "toscana", "capannori": "toscana",
    "viareggio": "toscana", "scandicci": "toscana",
    "san giovanni valdarno": "toscana",
    "san-giovanni-valdarno": "toscana",
    # Veneto
    "venezia": "veneto", "verona": "veneto", "padova": "veneto",
    "vicenza": "veneto", "treviso": "veneto", "rovigo": "veneto",
    "belluno": "veneto", "chioggia": "veneto", "mestre": "veneto",
    "marghera": "veneto", "mira": "veneto", "spinea": "veneto",
    "abano terme": "veneto", "abano-terme": "veneto",
    "albignasego": "veneto", "cittadella": "veneto", "este": "veneto",
    "monselice": "veneto", "piove di sacco": "veneto",
    "piove-di-sacco": "veneto", "san dona di piave": "veneto",
    "san-dona-di-piave": "veneto", "thiene": "veneto", "valdagno": "veneto",
    "arzignano": "veneto", "bassano del grappa": "veneto",
    "bassano-del-grappa": "veneto", "conegliano": "veneto",
    "vittorio veneto": "veneto", "vittorio-veneto": "veneto",
    "castelfranco veneto": "veneto", "castelfranco-veneto": "veneto",
    "mogliano veneto": "veneto", "mogliano-veneto": "veneto",
    "san dona": "veneto", "san-dona": "veneto",
    "jesolo": "veneto", "caorle": "veneto", "schio": "veneto",
    # Friuli Venezia Giulia
    "trieste": "friuli-venezia-giulia", "udine": "friuli-venezia-giulia",
    "pordenone": "friuli-venezia-giulia", "gorizia": "friuli-venezia-giulia",
    # Puglia
    "bari": "puglia", "taranto": "puglia", "lecce": "puglia",
    "brindisi": "puglia", "foggia": "puglia", "barletta": "puglia",
    "andria": "puglia", "trani": "puglia", "altamura": "puglia",
    "bisceglie": "puglia", "bitonto": "puglia", "molfetta": "puglia",
    "monopoli": "puglia",
    # Marche
    "ancona": "marche", "pesaro": "marche", "urbino": "marche",
    "pesaro-urbino": "marche", "ascoli piceno": "marche",
    "ascoli-piceno": "marche", "fermo": "marche", "macerata": "marche",
    "fano": "marche",
    # Abruzzo
    "pescara": "abruzzo", "chieti": "abruzzo", "teramo": "abruzzo",
    "l aquila": "abruzzo", "laquila": "abruzzo", "l-aquila": "abruzzo",
    # Molise
    "campobasso": "molise", "isernia": "molise",
    # Basilicata
    "potenza": "basilicata", "matera": "basilicata",
    # Calabria
    "catanzaro": "calabria", "cosenza": "calabria", "crotone": "calabria",
    "vibo valentia": "calabria", "vibo-valentia": "calabria",
    "reggio calabria": "calabria", "reggio-calabria": "calabria",
    # Sardegna
    "cagliari": "sardegna", "sassari": "sardegna", "nuoro": "sardegna",
    "oristano": "sardegna", "olbia": "sardegna",
    "olbia-tempio": "sardegna", "carbonia": "sardegna",
    "iglesias": "sardegna", "alghero": "sardegna",
    # Umbria
    "perugia": "umbria", "terni": "umbria",
    # Trentino-Alto Adige
    "trento": "trentino-alto-adige", "bolzano": "trentino-alto-adige",
    # Valle d'Aosta
    "aosta": "valle-d-aosta",
    # Lazio (south of Roma metro)
    "sora": "lazio",
}


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


def _find_regions(text: str) -> set[str]:
    """Return the set of regions named in `text`, in canonical form.

    Same matching strategy as _find_comuni: exact-token for single-word
    regions ("lazio", "veneto"), contiguous-token-window for multi-word,
    plus a glued-token exact match for forms like "friuliveneziagiulia"
    that appear as single tokens in domains.
    """
    if not text:
        return set()
    tokens = [t for t in _TOKEN_SEP_RE.split(_normalise(text)) if t]
    if not tokens:
        return set()

    found: set[str] = set()
    for region in _REGIONS_SORTED:
        canonical = _REGION_CANONICAL.get(region, region)
        if canonical in found:
            continue
        parts = region.split()
        if len(parts) == 1:
            target = parts[0]
            for tok in tokens:
                if tok == target:
                    found.add(canonical)
                    break
        else:
            n = len(parts)
            for i in range(len(tokens) - n + 1):
                if tokens[i : i + n] == parts:
                    found.add(canonical)
                    break
    return found


def _regions_for_comuni(comuni: set[str]) -> set[str]:
    """Map a set of comuni to the canonical regions they belong to.

    Comuni without a known region (whitelist not yet extended) contribute
    nothing — the region scope check then effectively skips them, which is
    the conservative behaviour.
    """
    return {_COMUNE_TO_REGION[c] for c in comuni if c in _COMUNE_TO_REGION}


def filter_resources(
    resources: Iterable[Resource], query: str
) -> list[Resource]:
    """Drop resources from a different comune OR region than the query.

    Decision per resource (in order):
      - query mentions no comune → keep all (no scoping signal to apply).
      - resource URL+name mention a comune in the wanted set → keep.
      - resource URL+name mention a comune outside the wanted set → drop.
      - resource URL+name mention a region in the wanted regions → keep
        (national or regional catalogue genuinely covering the place).
      - resource URL+name mention a region outside the wanted regions → drop
        (e.g. piste ciclabili Bologna → drop dati.friuliveneziagiulia.it).
      - resource mentions neither comune nor region → keep (national /
        cross-region aggregate; still potentially relevant).
    """
    resources = list(resources)
    wanted = extract_places(query)
    if not wanted:
        return resources

    wanted_regions = _regions_for_comuni(wanted)
    kept: list[Resource] = []
    dropped: list[tuple[str, str, set[str], set[str]]] = []
    for r in resources:
        haystack = f"{r.url} {r.name or ''}"
        present_comuni = _find_comuni(haystack)
        if present_comuni:
            if present_comuni & wanted:
                kept.append(r)
            else:
                dropped.append((r.url, "comune", present_comuni, set()))
            continue
        # No comune in URL → fall back to region scope (only when we know
        # the query's regions; otherwise we lack a meaningful comparison).
        if wanted_regions:
            present_regions = _find_regions(haystack)
            if present_regions:
                if present_regions & wanted_regions:
                    kept.append(r)
                else:
                    dropped.append((r.url, "regione", set(), present_regions))
                continue
        # Neither comune nor an off-region region detected → keep
        # (national/aggregate catalogue, still potentially relevant).
        kept.append(r)

    if dropped:
        log.info(
            "geo_filter: query=%s regions=%s kept=%d dropped=%d (samples=%s)",
            sorted(wanted),
            sorted(wanted_regions),
            len(kept),
            len(dropped),
            [
                f"{url[:80]}… [{scope}]→{sorted(comuni or regions)}"
                for url, scope, comuni, regions in dropped[:3]
            ],
        )
    return kept
