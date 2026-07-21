"""Politica Open Data + Piano di pubblicazione generati (#174, D3 di #170).

Motore **puro**: costruisce la STRUTTURA deterministica della *Politica Open Data*
(atto di indirizzo) e del *Piano di pubblicazione* dell'ente, a partire dai
candidati prioritizzati (D2). La prosa amministrativa può essere arricchita dal
backend via LLM (R11); qui la versione deterministica È il **fallback offline**.

I metadati **DCAT-AP_IT** per ogni voce del piano riusano `quality.generate_dcat`
(campi editoriali deducibili compilati, il resto `<da compilare>` — mai inventati)
e sono validabili con `quality.validate_dcat`.

Allineato alle Linee Guida AGID open data (Det. 183/2023), al paniere HVD
(Reg. UE 2023/138) e alle licenze IODL 2.0 / CC-BY 4.0.
"""

from __future__ import annotations

from collections.abc import Iterable

from jinja2 import Template
from pydantic import BaseModel

from opendata_core.quality import generate_dcat

from .prioritize import RankedCandidate

#: Licenza consigliata di default (l'alternativa italiana è IODL-2.0).
LICENZA_CONSIGLIATA = "CC-BY-4.0"

#: Cadenza di refresh di default per area (euristica; l'ente può correggerla).
_CADENZA_AREA: dict[str, str] = {
    "Ambiente": "trimestrale",
    "Mobilità": "mensile",
    "Anagrafe": "annuale",
    "Tributi": "annuale",
    "Contabilità": "annuale",
    "Appalti": "annuale",
    "Fondi e progetti": "semestrale",
    "SIT": "annuale",
    "Patrimonio": "annuale",
    "Cultura e turismo": "mensile",
    "SUAP/SUE": "trimestrale",
    "Atti": "continua",
}

#: Ufficio titolare di default per area (routing leggero; #181/D10 lo raffina).
_UFFICIO_AREA: dict[str, str] = {
    "Tributi": "Ufficio Tributi",
    "Contabilità": "Ragioneria",
    "Appalti": "Ufficio Gare e Contratti",
    "Fondi e progetti": "Ufficio Programmazione / Fondi",
    "Anagrafe": "Servizi Demografici",
    "SIT": "Ufficio SIT / Urbanistica",
    "Patrimonio": "Ufficio Patrimonio",
    "Ambiente": "Ufficio Ambiente",
    "Mobilità": "Ufficio Mobilità",
    "Cultura e turismo": "Ufficio Cultura",
    "SUAP/SUE": "SUAP / SUE",
    "Atti": "Segreteria / Protocollo",
}

#: Mappa categoria HVD → tema EU (dcat:theme) quando ovvio; altrimenti None
#: (`generate_dcat` lascia il placeholder — mai inventato).
_HVD_TEMA_EU: dict[str, str] = {
    "earth_observation_environment": "ENVI",
    "mobility": "TRAN",
    "geospatial": "REGI",
    "statistics": "ECON",
    "meteorological": "ENVI",
    "companies_ownership": "ECON",
}


class PianoVoce(BaseModel):
    """Una riga del Piano di pubblicazione (un dataset candidato)."""

    candidate_id: str
    nome: str
    area: str
    quadrante: str
    cadenza: str
    ufficio: str
    licenza: str
    privacy: str
    metadati_dcat: dict
    campi_dcat_mancanti: list[str]
    motivazione: str


class Piano(BaseModel):
    """Piano di pubblicazione: voci prioritizzate + lotto quick-win."""

    ente: str
    licenza: str
    voci: list[PianoVoce]
    quick_win: list[str]  # candidate_id del lotto Priorità 1


class SezionePolitica(BaseModel):
    titolo: str
    testo: str


class Politica(BaseModel):
    """Bozza di Politica Open Data (atto di indirizzo)."""

    titolo: str
    ente: str
    licenza: str
    sezioni: list[SezionePolitica]


def _cadenza(area: str) -> str:
    return _CADENZA_AREA.get(area, "annuale")


def _ufficio(area: str) -> str:
    return _UFFICIO_AREA.get(area, "RTD (Responsabile Transizione Digitale)")


def build_piano(
    ranked: Iterable[RankedCandidate], *, ente: str, licenza: str = LICENZA_CONSIGLIATA
) -> Piano:
    """Costruisce il Piano di pubblicazione dai candidati prioritizzati (D2).

    Per ogni voce: cadenza + ufficio titolare (euristica) e metadati DCAT-AP_IT
    precompilati (deducibili dal candidato; il resto `<da compilare>`).
    """
    voci: list[PianoVoce] = []
    quick_win: list[str] = []
    for r in ranked:
        c = r.candidate
        cadenza = _cadenza(c.area)
        dcat = generate_dcat(
            {},  # nessun file: template editoriale precompilato
            titolo=c.nome,
            descrizione=c.descrizione,
            licenza=licenza,
            ente=ente,
            tema=_HVD_TEMA_EU.get(c.hvd) if c.hvd else None,
            frequenza=cadenza,
        )
        voci.append(PianoVoce(
            candidate_id=c.id, nome=c.nome, area=c.area, quadrante=r.quadrante,
            cadenza=cadenza, ufficio=_ufficio(c.area), licenza=licenza,
            privacy=c.privacy, metadati_dcat=dcat,
            campi_dcat_mancanti=dcat.get("campi_mancanti", []),
            motivazione=r.motivazione,
        ))
        if r.quadrante == "quick_win":
            quick_win.append(c.id)
    return Piano(ente=ente, licenza=licenza, voci=voci, quick_win=quick_win)


def build_politica(*, ente: str, licenza: str = LICENZA_CONSIGLIATA) -> Politica:
    """Bozza deterministica della Politica Open Data (fallback offline, R11).

    Il backend può rigenerare la prosa di ogni sezione via LLM mantenendo la
    stessa struttura; senza LLM questa versione è già un atto di indirizzo valido.
    """
    sezioni = [
        SezionePolitica(
            titolo="1. Finalità",
            testo=(
                f"Il Comune di {ente} adotta gli open data come modalità ordinaria di "
                "pubblicazione dei propri dati, per trasparenza, riuso e valore per il "
                "territorio. I dati aperti sono l'unica fonte ufficiale: nessuna copia "
                "parallela sostituisce il portale."
            ),
        ),
        SezionePolitica(
            titolo="2. Ambito e principi",
            testo=(
                "Open by default: i dati non personali sono pubblicati in formati aperti "
                "e machine-readable, con metadati conformi a DCAT-AP_IT e indicizzati sul "
                "portale regionale/nazionale. Priorità ai dataset ad alto valore (HVD, "
                "Reg. UE 2023/138)."
            ),
        ),
        SezionePolitica(
            titolo="3. Licenza",
            testo=(
                f"La licenza standard è {licenza} (in alternativa IODL 2.0), che consente "
                "il riuso anche commerciale con attribuzione."
            ),
        ),
        SezionePolitica(
            titolo="4. Ruoli e responsabilità",
            testo=(
                "RTD: responsabile del coordinamento e del piano di pubblicazione. "
                "Uffici titolari del dato: produzione ed estrazione. DPO: validazione "
                "privacy sui dati sensibili (nessun dato personale è pubblicato senza il "
                "suo via libera). Referente open data: qualità e aggiornamento."
            ),
        ),
        SezionePolitica(
            titolo="5. Qualità e aggiornamento",
            testo=(
                "Ogni dataset ha una cadenza di aggiornamento dichiarata e controlli di "
                "qualità (completezza, formati, freschezza) prima della pubblicazione e "
                "nel tempo (monitoraggio automatico)."
            ),
        ),
        SezionePolitica(
            titolo="6. Riferimenti normativi",
            testo=(
                "CAD (D.Lgs 82/2005), Linee Guida AGID sull'open data (Det. 183/2023), "
                "Direttiva UE 2019/1024 e Reg. UE 2023/138 (High-Value Datasets), GDPR "
                "(Reg. UE 2016/679) per la de-identificazione."
            ),
        ),
    ]
    return Politica(
        titolo=f"Politica Open Data del Comune di {ente}",
        ente=ente, licenza=licenza, sezioni=sezioni,
    )


_POLITICA_MD = Template(
    "# {{ p.titolo }}\n\n"
    "> Bozza generata dal Copilota Open Data. Licenza standard: **{{ p.licenza }}**.\n"
    "{% for s in p.sezioni %}\n## {{ s.titolo }}\n\n{{ s.testo }}\n{% endfor %}"
)

_PIANO_MD = Template(
    "# Piano di pubblicazione — Comune di {{ pl.ente }}\n\n"
    "Licenza standard: **{{ pl.licenza }}**. Voci: {{ pl.voci|length }} "
    "(quick win: {{ pl.quick_win|length }}).\n\n"
    "| Priorità | Dataset | Area | Cadenza | Ufficio | Privacy |\n"
    "|---|---|---|---|---|---|\n"
    "{% for v in pl.voci %}| {{ v.quadrante }} | {{ v.nome }} | {{ v.area }} | "
    "{{ v.cadenza }} | {{ v.ufficio }} | {{ v.privacy }} |\n{% endfor %}"
)


def render_politica_markdown(p: Politica) -> str:
    return _POLITICA_MD.render(p=p)


def render_piano_markdown(pl: Piano) -> str:
    return _PIANO_MD.render(pl=pl)
