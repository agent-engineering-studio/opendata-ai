"""SDMX 2.1 REST async client (ISTAT, Eurostat, OECD)."""

from .asia import fetch_imprese_comune
from .client import SdmxClient, SdmxError, data_path, df_ref
from .turismo import fetch_ricettivita_comune

__all__ = [
    "SdmxClient",
    "SdmxError",
    "data_path",
    "df_ref",
    "fetch_imprese_comune",
    "fetch_ricettivita_comune",
]
