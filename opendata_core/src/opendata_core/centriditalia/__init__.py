"""Client per Centri d'Italia (openpolis): mirror locale dei CSV bulk + query.

Dati sull'accoglienza migranti in Italia (centri CAS/CPA/hotspot, progetti e
strutture SAI). NON è un'API REST: file CSV bulk su S3 caricati in un mirror
SQLite locale. Licenza dati: CC-BY 4.0 (openpolis / Centri d'Italia).
"""

from .client import CentriDItaliaClient, CentriDItaliaError
from .mapping import LICENZA, METADATI_URL

__all__ = [
    "CentriDItaliaClient",
    "CentriDItaliaError",
    "LICENZA",
    "METADATI_URL",
]
