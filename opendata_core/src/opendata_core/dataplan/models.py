"""Modelli del Copilota Open Data (#170 / D1 #172): dataset candidato all'apertura.

Un `CandidateDataset` è una voce del catalogo "applicativi/adempimenti comunali →
dataset open candidati": NON un dataset esistente, ma un dato che il comune
*potrebbe/dovrebbe* aprire, con le informazioni che servono a prioritizzarlo (D2).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator

from opendata_core.maturity.coverage import HVD_LABELS

#: Slug delle 6 categorie HVD (Reg. UE 2023/138), allineate a maturity/coverage.
HVD_CATEGORIES = frozenset(HVD_LABELS)

#: Sensibilità privacy della fonte (D4): nessun dato personale / solo aggregati /
#: contiene dati personali (→ de-identificazione obbligatoria prima di aprire).
Privacy = Literal["nullo", "aggregato", "personale"]

#: Sforzo stimato di pubblicazione.
Sforzo = Literal["basso", "medio", "alto"]


class GiaAperto(BaseModel):
    """Il dato è già aperto altrove (adempimento nazionale) → si LINKA, non si riproduce."""

    fonte: str            # es. "BDAP/SIOPE", "ANAC", "OpenCoesione", "OpenPNRR", "ISTAT"
    connettore: str | None = None  # MCP/connettore che lo raggiunge già, se presente


class CandidateDataset(BaseModel):
    """Una voce del catalogo D1 (#172)."""

    id: str
    nome: str
    area: str               # Tributi, Contabilità, Appalti, SIT, Ambiente, Mobilità, …
    fonte_interna: str      # gestionale/adempimento che produce il dato
    descrizione: str        # in linguaggio d'ufficio
    hvd: str | None = None  # categoria HVD (slug) o None se non-HVD
    gia_aperto: GiaAperto | None = None
    privacy: Privacy = "nullo"
    sforzo: Sforzo = "medio"
    #: analisi/lente/use-case della piattaforma che il dato *sblocca* (segnale di
    #: riuso reale — pesa nella prioritizzazione D2). Vuoto = nessuno noto.
    sblocca: list[str] = []

    @field_validator("hvd")
    @classmethod
    def _hvd_valido(cls, v: str | None) -> str | None:
        if v is not None and v not in HVD_CATEGORIES:
            raise ValueError(
                f"categoria HVD {v!r} non valida; ammesse: {', '.join(sorted(HVD_CATEGORIES))}"
            )
        return v
