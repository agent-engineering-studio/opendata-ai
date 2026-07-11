"""Modello della zonizzazione PUG/PRG consultata come open data (#129, Fase 3)."""

from __future__ import annotations

from pydantic import BaseModel


class PugZoning(BaseModel):
    """Zonizzazione urbanistica (PUG/PRG) di un comune, letta DAL VIVO da un dataset
    open data (CKAN → GeoJSON). Nessuna copia memorizzata: è la fonte ufficiale
    pubblicata dal comune/regione. ``zone_key`` è l'attributo del GeoJSON che porta
    la zona omogenea (B/C/D/E/F…), rilevato euristicamente (schema non standard tra
    portali). ``None`` a monte = PUG non pubblicato come open data interrogabile."""

    zone_key: str
    features: list[dict]  # feature GeoJSON (poligoni di zona)
    dataset_title: str
    source_url: str
    licenza: str
