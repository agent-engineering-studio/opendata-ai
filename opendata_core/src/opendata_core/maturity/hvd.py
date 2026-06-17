"""Match High-Value Dataset (Reg. UE 2023/138): 6 categorie, euristica keyword.

Categorie: geospatial, earth_observation_environment, meteorological, statistics,
companies_ownership, mobility. Match deterministico su titolo/descrizione/tag/theme.
"""

from __future__ import annotations

import re

from .models import DatasetInput

# Ordine = priorità in caso di match multipli. Keyword IT + EN, lowercase. Il match
# è a confine di parola come PREFISSO (\bkw), così "trasport" coglie trasporti/o ma
# "vento" non scatta dentro "evento".
HVD_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("mobility", (
        "mobilità", "mobility", "trasport", "traffico", "gtfs", "orari", "fermate",
        "parcheggi", "piste ciclabili", "tpl", "autobus", "treni",
    )),
    ("meteorological", (
        "meteo", "meteorolog", "temperatura", "precipitazion", "vento", "previsioni",
        "weather", "climatolog",
    )),
    ("geospatial", (
        "geospatial", "cartograf", "confini", "catasto", "indirizz", "mappa", "mappe",
        "gis", "coordinate", "toponom", "particelle", "civici",
    )),
    ("earth_observation_environment", (
        "ambient", "emission", "qualità dell'aria", "rifiut", "acqua", "suolo",
        "biodiversità", "energia", "satellitar", "inquinament", "environment",
    )),
    ("statistics", (
        "statistic", "popolazione", "censiment", "demografi", "istat", "occupazion",
        "reddito", "pil", "indicatori",
    )),
    ("companies_ownership", (
        "impres", "società", "partita iva", "registro imprese", "aziend",
        "camera di commercio", "company", "ownership", "appalt", "contratti",
    )),
]


def _matches(blob: str, kw: str) -> bool:
    # Confine di parola come prefisso: \btrasport coglie "trasporti"; \bvento
    # NON scatta in "evento". Le keyword multi-parola (es. "piste ciclabili")
    # restano substring (contengono già spazi).
    return re.search(r"\b" + re.escape(kw), blob) is not None


def match_hvd_category(ds: DatasetInput) -> str | None:
    """Ritorna la categoria HVD del dataset (per priorità), o None."""
    blob = ds.keyword_blob
    for category, keywords in HVD_KEYWORDS:
        if any(_matches(blob, kw) for kw in keywords):
            return category
    return None
