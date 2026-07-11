"""Modelli Pydantic degli indicatori di rischio IdroGEO (livello comunale)."""

from __future__ import annotations

from pydantic import BaseModel


class HazardSlice(BaseModel):
    """Una classe di pericolosità: superficie e popolazione esposte."""

    classe: str  # p4 | p3 | p2 | p1 | aa | p3p4 (aggregato frane)
    area_kmq: float | None = None
    area_pct: float | None = None
    popolazione: int | None = None
    popolazione_pct: float | None = None


class LandCoverInfo(BaseModel):
    """Copertura del suolo in un punto, da Corine Land Cover ISPRA (#128, Fase 2c).

    Interrogazione PUNTUALE via WMS GetFeatureInfo sul layer CLC nazionale: risolve
    il nodo "edificato/impermeabilizzato" §4.3 lasciato "da verificare" in Fase 1.
    ``macroclasse`` è la prima cifra del codice CLC (1=artificiale, 2=agricolo,
    3=boschi/seminaturale, 4=zone umide, 5=corpi idrici)."""

    clc_code: str  # codice CLC (es. "111" tessuto urbano continuo)
    macroclasse: int  # 1..5 (prima cifra del codice)
    descrizione: str  # etichetta della macroclasse
    impermeabilizzato: bool  # macroclasse == 1 (superfici artificiali)
    source_url: str
    licenza: str


class RiskIndicators(BaseModel):
    """Indicatori di pericolosità frane + idraulica per un comune.

    Le classi sono ordinate dalla più severa; ``frane_p3p4`` è l'aggregato
    "pericolosità elevata o molto elevata" — il numero che conta per i
    vincoli di espansione (spec 07).
    """

    cod_comune: str
    nome: str
    area_kmq: float | None = None
    popolazione_residente: int | None = None
    frane: list[HazardSlice] = []
    frane_p3p4: HazardSlice | None = None
    idraulica: list[HazardSlice] = []
    source_url: str
    licenza: str
