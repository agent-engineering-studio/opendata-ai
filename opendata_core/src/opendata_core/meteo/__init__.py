"""Client Open-Meteo (previsioni meteo, nessuna API key). Licenza dati: CC BY 4.0."""

from .client import OPEN_METEO_LICENSE, MeteoError, forecast

__all__ = ["forecast", "MeteoError", "OPEN_METEO_LICENSE"]
