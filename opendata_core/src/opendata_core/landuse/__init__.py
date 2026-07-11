"""Riconciliazione OSM ↔ stato reale del suolo — motore puro (#127).

Vedi `reconcile.py`: costruisce il record §4.5 per poligono con le sole fonti
disponibili oggi (OSM + IdroGEO PAI + OpenCoesione), modellando l'incertezza come
confidenza graduata invece che come blocco.
"""

from .reconcile import Confidenza, SoilRecord, reconcile_polygon

__all__ = ["SoilRecord", "reconcile_polygon", "Confidenza"]
