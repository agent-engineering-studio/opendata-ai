"""Modelli dell'Idea Lab — percorso conversazionale dai dati all'idea.

Il percorso è STATELESS: il client rimanda a ogni turno l'intera
conversazione più i dataset già scoperti (campo `datasets` della risposta
precedente), così il backend non tiene sessioni e la UI statica resta
compatibile con l'export GitHub Pages.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Tappe del percorso di brainstorming, in ordine. Il coach può restare sulla
# stessa tappa o avanzare di una; non si torna indietro (il client può sempre
# ricominciare azzerando la conversazione).
STAGES: tuple[str, ...] = (
    "inquadramento",
    "esplorazione",
    "divergenza",
    "convergenza",
    "sintesi",
)

STAGE_LABELS: dict[str, str] = {
    "inquadramento": "Inquadra la sfida",
    "esplorazione": "Esplora i dati",
    "divergenza": "Genera idee",
    "convergenza": "Scegli e critica",
    "sintesi": "Scheda finale",
}

Area = Literal["salute", "ambiente", "territorio", "turismo"]

# Per area: label UI, keyword di ricerca CKAN, tema OpenCoesione per i
# progetti comparabili finanziati (slug di opendata_core.opencoesione.TEMI).
AREAS: dict[str, dict[str, str]] = {
    "salute": {
        "label": "Salute",
        "keywords": "salute sanità farmacie ospedali assistenza prevenzione",
        "oc_tema": "inclusione-sociale",
    },
    "ambiente": {
        "label": "Ambiente",
        "keywords": "ambiente rifiuti aria acqua energia verde inquinamento",
        "oc_tema": "ambiente",
    },
    "territorio": {
        "label": "Territorio",
        "keywords": "territorio urbanistica mobilità trasporti commercio lavoro",
        "oc_tema": "reti-servizi-digitali",
    },
    "turismo": {
        "label": "Turismo",
        "keywords": "turismo cultura eventi musei ricettività itinerari",
        "oc_tema": "cultura-e-turismo",
    },
}


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class IdeaDataset(BaseModel):
    """Dataset citabile: metadati CKAN + qualità calcolata (assess_quality)."""

    id: str
    title: str
    url: str = ""
    notes: str = ""
    organization: str = ""
    formats: list[str] = Field(default_factory=list)
    modified: str | None = None
    stars: int = 0
    license_open: bool = False
    freshness_days: int | None = None
    quality_note: str = ""


class FundingProject(BaseModel):
    """Progetto comparabile già finanziato (OpenCoesione) — evidenza di finanziabilità."""

    clp: str
    titolo: str
    tema: str | None = None
    stato: str | None = None
    ciclo: str | None = None
    finanziamento_totale: float | None = None
    url: str | None = None


class IdeaChatRequest(BaseModel):
    """Il portale CKAN NON è per-richiesta: è fissato dai settings (ideas_portal_
    base_url + fq coerenti tra loro), sia per evitare SSRF verso host arbitrari
    sia perché l'fq regionale avrebbe senso solo sul portale configurato."""

    messages: list[ChatMessage]
    area: Area | None = None
    territory: str | None = None
    # "sfida": si parte da un problema aperto e si converge verso un'idea.
    # "idea": l'idea c'è già — il percorso mappa il fabbisogno di dati
    # (quali servono, quali esistono, quali mancano) per realizzarla.
    mode: Literal["sfida", "idea"] = "sfida"
    # Tappa corrente: il client rimanda quella dell'ultima risposta.
    stage: str | None = None
    # Dataset e progetti finanziati già scoperti, rimandati dal client.
    datasets: list[IdeaDataset] | None = None
    funding: list[FundingProject] | None = None


class IdeaChatResponse(BaseModel):
    reply: str
    stage: str
    stage_label: str
    datasets: list[IdeaDataset] = Field(default_factory=list)
    funding: list[FundingProject] = Field(default_factory=list)
    # Risposte rapide proposte all'utente (max 3).
    suggestions: list[str] = Field(default_factory=list)
    # True quando il percorso è alla sintesi: la UI mostra "Genera la scheda".
    report_ready: bool = False
    offline: bool = False


class IdeaSpunto(BaseModel):
    """Direzione d'idea proposta dalla pre-analisi di un'area."""

    titolo: str
    descrizione: str = ""


class IdeaScoutRequest(BaseModel):
    area: Area
    territory: str | None = None


class IdeaScoutResponse(BaseModel):
    datasets: list[IdeaDataset] = Field(default_factory=list)
    funding: list[FundingProject] = Field(default_factory=list)
    spunti: list[IdeaSpunto] = Field(default_factory=list)
    offline: bool = False


class IdeaReportRequest(BaseModel):
    messages: list[ChatMessage]
    area: Area | None = None
    territory: str | None = None
    datasets: list[IdeaDataset] | None = None
    funding: list[FundingProject] | None = None
    # Titolo dell'idea scelta in convergenza (se l'utente ne ha selezionata una).
    idea_titolo: str | None = None


class IdeaReportResponse(BaseModel):
    report_md: str
    idea_id: str
    titolo: str
    generato_il: str
    offline: bool = False
