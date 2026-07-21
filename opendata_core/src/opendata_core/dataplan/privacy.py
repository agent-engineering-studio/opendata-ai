"""Regole privacy/GDPR per famiglia di dato (#175, D4 di #170).

Motore **puro e deterministico**: dice, per famiglia di dato comunale, COSA
rimuovere, COSA aggregare, con quale **granularità minima** e **soglia di
k-anonimato**, e se serve la **validazione umana del DPO**. Alimenta l'export
brief (D9) e il loop qualità (D12).

Vincolo non negoziabile (§7 della guida): **nessun dato personale è pubblicato
senza validazione umana**. Quando la fonte contiene dati personali
(`privacy="personale"`) o la famiglia lo richiede, la checklist marca sempre
`richiede_validazione_umana=True`.

Regole codificate qui (non YAML) perché intrecciate alla logica di soglia; la
mappa area→famiglia copre il catalogo D1 e le famiglie citate nell'issue (sociale,
polizia locale) anche se non ancora presenti tra i candidati.
"""

from __future__ import annotations

from pydantic import BaseModel

from .models import CandidateDataset


class PrivacyRule(BaseModel):
    """Regola di de-identificazione/aggregazione per una famiglia di dato."""

    famiglia: str
    campi_da_rimuovere: list[str]
    campi_da_aggregare: list[str]
    granularita_minima: str
    k_anonimato: int              # celle con meno di k unità → soppresse/arrotondate
    richiede_validazione_dpo: bool
    note: str


class PrivacyChecklist(BaseModel):
    """Checklist applicabile in produzione (export brief / gate DPO)."""

    famiglia: str
    privacy_dichiarata: str       # dal catalogo: nullo | aggregato | personale
    campi_da_rimuovere: list[str]
    campi_da_aggregare: list[str]
    granularita_minima: str
    k_anonimato: int
    richiede_validazione_umana: bool
    passi: list[str]


_RULES: dict[str, PrivacyRule] = {
    "generico": PrivacyRule(
        famiglia="generico", campi_da_rimuovere=[], campi_da_aggregare=[],
        granularita_minima="nessun vincolo", k_anonimato=1,
        richiede_validazione_dpo=False,
        note="Dato non personale (patrimonio, ambiente, mobilità, cultura): pubblicabile.",
    ),
    "tributi": PrivacyRule(
        famiglia="tributi",
        campi_da_rimuovere=["codice_fiscale", "denominazione/nominativo", "indirizzo_immobile",
                            "identificativo_catastale"],
        campi_da_aggregare=["importi", "riscossioni", "numero_contribuenti"],
        granularita_minima="zona / quartiere (mai per contribuente o immobile)",
        k_anonimato=5, richiede_validazione_dpo=False,
        note="Solo totali/medie per zona; sopprimere le celle sotto la soglia k.",
    ),
    "anagrafe": PrivacyRule(
        famiglia="anagrafe",
        campi_da_rimuovere=["nome", "cognome", "codice_fiscale", "indirizzo",
                            "data_di_nascita_esatta"],
        campi_da_aggregare=["conteggi_popolazione"],
        granularita_minima="classi d'età (≥5 anni) × quartiere",
        k_anonimato=5, richiede_validazione_dpo=False,
        note="Solo aggregati demografici; niente quasi-identificatori incrociabili.",
    ),
    "edilizia_sue": PrivacyRule(
        famiglia="edilizia_sue",
        campi_da_rimuovere=["richiedente", "proprietario", "codice_fiscale",
                            "dati_progettista"],
        campi_da_aggregare=["pratiche per zona / tipologia"],
        granularita_minima="zona urbanistica (rimosso l'intestatario)",
        k_anonimato=5, richiede_validazione_dpo=True,
        note="Tenere il dato territoriale/tipologico; rimuovere ogni PII della persona.",
    ),
    "commercio_suap": PrivacyRule(
        famiglia="commercio_suap",
        campi_da_rimuovere=["titolare_persona_fisica", "codice_fiscale", "contatti_personali"],
        campi_da_aggregare=["esercizi per via / categoria (se il puntuale identifica una persona)"],
        granularita_minima="esercizio / insegna (dato d'impresa) — PII persone fisiche rimosse",
        k_anonimato=5, richiede_validazione_dpo=True,
        note="Le ditte individuali contengono dati personali: de-identificare l'intestatario.",
    ),
    "sociale": PrivacyRule(
        famiglia="sociale",
        campi_da_rimuovere=["ogni identificativo diretto", "dati sanitari/di bisogno"],
        campi_da_aggregare=["beneficiari per servizio / fascia"],
        granularita_minima="servizio × fascia (dato particolarmente sensibile)",
        k_anonimato=10, richiede_validazione_dpo=True,
        note="Categoria particolare (art. 9 GDPR): soglia k più alta, revisione DPO obbligatoria.",
    ),
    "polizia_locale": PrivacyRule(
        famiglia="polizia_locale",
        campi_da_rimuovere=["targa", "nominativo_sanzionato", "codice_fiscale"],
        campi_da_aggregare=["violazioni per tipo / zona / periodo"],
        granularita_minima="zona × periodo",
        k_anonimato=5, richiede_validazione_dpo=True,
        note="Nessun dato che identifichi il sanzionato; solo aggregati statistici.",
    ),
    "atti": PrivacyRule(
        famiglia="atti",
        campi_da_rimuovere=["dati personali nel corpo dell'atto"],
        campi_da_aggregare=[],
        granularita_minima="metadati dell'atto (oggetto, numero, data); contenuto solo se già pubblico (albo)",
        k_anonimato=1, richiede_validazione_dpo=True,
        note="Pubblicare i metadati come dataset; il contenuto richiede revisione umana.",
    ),
}

#: Mappa area del catalogo D1 → famiglia privacy (default: generico).
_AREA_TO_FAMILY: dict[str, str] = {
    "Tributi": "tributi",
    "Anagrafe": "anagrafe",
    "Atti": "atti",
    # "SUAP/SUE" è disambiguata per keyword in family_for (edilizia vs commercio).
}


def family_for(candidate: CandidateDataset) -> str:
    """Famiglia privacy del candidato (dall'area, con disambiguazione SUAP/SUE)."""
    area = candidate.area
    if area == "SUAP/SUE":
        blob = f"{candidate.id} {candidate.nome}".lower()
        if "ediliz" in blob:
            return "edilizia_sue"
        return "commercio_suap"
    return _AREA_TO_FAMILY.get(area, "generico")


def rules_for(family: str) -> PrivacyRule:
    """Regola della famiglia; `generico` se sconosciuta (fail-safe, mai KeyError)."""
    return _RULES.get(family, _RULES["generico"])


def all_families() -> tuple[str, ...]:
    return tuple(_RULES)


def checklist_for(candidate: CandidateDataset) -> PrivacyChecklist:
    """Checklist privacy per un candidato: regole + passi + gate umano.

    ``richiede_validazione_umana`` è True se il dato è personale o se la famiglia
    richiede il DPO — vincolo §7: niente pubblicazione di dati personali senza
    validazione umana.
    """
    fam = family_for(candidate)
    rule = rules_for(fam)
    human = candidate.privacy == "personale" or rule.richiede_validazione_dpo

    passi: list[str] = []
    if rule.campi_da_rimuovere:
        passi.append(f"Rimuovi i campi identificativi: {', '.join(rule.campi_da_rimuovere)}.")
    if rule.campi_da_aggregare:
        passi.append(f"Aggrega: {', '.join(rule.campi_da_aggregare)}.")
    if rule.k_anonimato > 1:
        passi.append(
            f"Granularità minima {rule.granularita_minima}; sopprimi/arrotonda le celle "
            f"con meno di {rule.k_anonimato} unità (k-anonimato)."
        )
    passi.append("Verifica che non restino quasi-identificatori incrociabili.")
    if human:
        passi.append("VALIDAZIONE DPO obbligatoria prima della pubblicazione (dato personale).")
    else:
        passi.append("Dato non personale: pubblicabile senza gate DPO.")

    return PrivacyChecklist(
        famiglia=fam,
        privacy_dichiarata=candidate.privacy,
        campi_da_rimuovere=rule.campi_da_rimuovere,
        campi_da_aggregare=rule.campi_da_aggregare,
        granularita_minima=rule.granularita_minima,
        k_anonimato=rule.k_anonimato,
        richiede_validazione_umana=human,
        passi=passi,
    )
