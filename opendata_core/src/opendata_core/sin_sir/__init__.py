"""Siti contaminati e bonifiche SIN-SIR (ISPRA MOSAICO) — connettore puro (#128 Fase 2a).

Vedi `client.py`: interrogazione puntuale (SIN, poligoni) + comunale (procedimenti
SIR, punti) del FeatureServer MOSAICO. Alimenta `reconcile_polygon` con il segnale
di contaminazione → classificazione BROWNFIELD (§4.4).
"""

from .client import SinSirClient
from .models import ContaminationInfo

__all__ = ["SinSirClient", "ContaminationInfo"]
