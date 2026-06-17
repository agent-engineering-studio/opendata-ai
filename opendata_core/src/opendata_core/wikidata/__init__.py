"""Client Wikidata SPARQL per l'arricchimento dei comuni. Dati: CC0."""

from .client import WIKIDATA_LICENSE, WikidataError, comune_by_istat

__all__ = ["comune_by_istat", "WikidataError", "WIKIDATA_LICENSE"]
