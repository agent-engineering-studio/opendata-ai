"""Zonizzazione PUG/PRG come open data interrogabile dal vivo (#129, Fase 3).

Vedi `client.py`: consulta il portale CKAN regionale per il dataset di zonizzazione
del comune e ne legge i poligoni di zona. Nessuna copia memorizzata: fonte ufficiale
o "non pubblicato" (→ domanda di riuso non soddisfatta).
"""

from .client import fetch_zoning, zone_at
from .models import PugZoning

__all__ = ["PugZoning", "fetch_zoning", "zone_at"]
