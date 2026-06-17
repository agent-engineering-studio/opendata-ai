"""Combinabilità: presenza di chiavi spaziali/temporali per il join con altri dataset."""

from __future__ import annotations

import re

from ..maturity.models import OPEN_FORMATS, DatasetInput
from .models import CombinabilityProfile

# Chiavi spaziali/temporali cercate a confine di parola come prefisso.
_SPATIAL_KW = (
    "istat", "comune", "provincia", "regione", "cap", "coordinate", "latitudin",
    "longitudin", "nuts", "indirizz", "civico", "confine", "quartier", "zona", "geo",
)
_TEMPORAL_KW = ("anno", "anni", "data", "date", "periodo", "mese", "trimestr", "semestr", "year", "time")
# Formati intrinsecamente geospaziali → chiave spaziale implicita.
_SPATIAL_FORMATS = {"geojson", "kml", "gml", "shp", "wkt", "gpx"}


def _found(blob: str, keywords: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(kw for kw in keywords if re.search(r"\b" + re.escape(kw), blob))


def combinability(ds: DatasetInput) -> CombinabilityProfile:
    """Profilo di combinabilità del dataset (chiavi + score 0–100)."""
    blob = ds.keyword_blob
    fmts = {f.lower() for f in ds.formats}

    spatial = list(_found(blob, _SPATIAL_KW))
    if fmts & _SPATIAL_FORMATS:
        spatial.append("formato-geo")
    temporal = list(_found(blob, _TEMPORAL_KW))
    if ds.frequency:
        temporal.append("frequenza")

    has_spatial = bool(spatial)
    has_temporal = bool(temporal)
    open_fmt = bool(fmts & OPEN_FORMATS)
    score = 40.0 * has_spatial + 35.0 * has_temporal + 25.0 * open_fmt

    return CombinabilityProfile(
        spatial_keys=tuple(dict.fromkeys(spatial)),
        temporal_keys=tuple(dict.fromkeys(temporal)),
        score=round(score, 1),
    )
