"""Idee/proposte a livello regionale (#230, F3 di #227) — motore PURO.

Aggrega i candidati Copilota (D1/D2 di #170) con la copertura reale dei comuni
della regione: un dataset che manca in *più* comuni e ha *più valore* diventa una
priorità regionale (es. «12/30 comuni non hanno pubblicato i rifiuti → dataset
regionale prioritario»). I candidati sono iniettati (nessuna dipendenza dal
catalogo qui): il backend passa il ranking del Copilota già calcolato.
"""

from __future__ import annotations

from pydantic import BaseModel

from .models import ComuneSummary

# La priorità pesa il valore Copilota per il "gap" regionale: un dataset già
# coperto ovunque conta comunque un po' (0.3), uno mancante ovunque conta pieno.
_GAP_FLOOR = 0.3
# Gap "neutro" quando la copertura non è misurabile (candidato senza HVD).
_UNKNOWN_GAP = 0.5


class IdeaCandidate(BaseModel):
    """Candidato Copilota, ridotto ai campi che servono all'aggregazione."""

    id: str
    nome: str
    area: str
    hvd: str | None = None
    valore: int  # 0..100 dal prioritize del Copilota


class RegionIdea(BaseModel):
    id: str
    nome: str
    area: str
    hvd: str | None
    valore: int
    comuni_totali: int
    comuni_con: int | None       # None = copertura non misurabile (no HVD)
    comuni_mancanti: int | None
    copertura: float | None      # comuni_con / comuni_totali
    priorita: float              # 0..100
    motivo: str


def regional_ideas(
    candidates: list[IdeaCandidate],
    comuni: list[ComuneSummary],
    *,
    comuni_totali: int | None = None,
) -> list[RegionIdea]:
    """Priorità regionale dei dataset, dalla più alta. Deterministico."""
    total = comuni_totali if comuni_totali is not None else len(comuni)
    out: list[RegionIdea] = []
    for c in candidates:
        if c.hvd and total:
            con = sum(1 for x in comuni if c.hvd in x.hvd_categorie)
            mancanti = max(0, total - con)
            copertura = round(con / total, 3)
            gap = mancanti / total
            motivo = f"mancante in {mancanti}/{total} comuni della regione"
            if c.valore >= 60:
                motivo += "; alto valore"
        else:
            con = mancanti = copertura = None
            gap = _UNKNOWN_GAP
            motivo = "priorità da valore (copertura non misurabile)"
        priorita = round(c.valore * (_GAP_FLOOR + (1 - _GAP_FLOOR) * gap), 1)
        out.append(
            RegionIdea(
                id=c.id, nome=c.nome, area=c.area, hvd=c.hvd, valore=c.valore,
                comuni_totali=total, comuni_con=con, comuni_mancanti=mancanti,
                copertura=copertura, priorita=priorita, motivo=motivo,
            )
        )
    out.sort(key=lambda i: (-i.priorita, i.id))
    return out
