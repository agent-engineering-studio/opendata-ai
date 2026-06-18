"""Guida operativa open-data per enti senza (o con pochi) dati pubblicati.

Quando l'harvest trova dati insufficienti, NON si inventano punteggi: si restituisce
una **guida operativa** ancorata alle linee guida ufficiali AGID/DCAT-AP_IT, che
indirizza il comune verso una politica di open data. Pura (niente I/O): il testo è un
manuale strutturato personalizzato col nome dell'ente e con cosa manca.

Riferimenti istituzionali citati (portali ufficiali):
  - Linee guida AGID "Open Data" — docs.italia.it
  - Profilo di metadati DCAT-AP_IT — schema.gov.it
  - Catalogo nazionale — dati.gov.it
  - Dataset a elevato valore (HVD) — regolamento UE 2023/138
"""

from __future__ import annotations

from typing import Any

_REF_AGID = {
    "label": "Linee guida AGID sull'Open Data",
    "url": "https://docs.italia.it/italia/daf/lg-patrimonio-pubblico/it/stabile/index.html",
}
_REF_DCAT = {
    "label": "Profilo DCAT-AP_IT (metadati)",
    "url": "https://schema.gov.it/lov/DCAT-AP_IT",
}
_REF_DATIGOV = {"label": "Catalogo nazionale dati.gov.it", "url": "https://www.dati.gov.it/"}
_REF_HVD = {
    "label": "Dataset a elevato valore (HVD) — Reg. UE 2023/138",
    "url": "https://eur-lex.europa.eu/eli/reg_impl/2023/138/oj",
}
_REF_LICENZE = {
    "label": "Licenze aperte (CC-BY 4.0 / IODL 2.0)",
    "url": "https://www.dati.gov.it/content/italian-open-data-license-v20",
}


def build_guida_opendata(
    entity_name: str,
    *,
    n_datasets: int = 0,
    total_on_portal: int = 0,
    open_license_ratio: float | None = None,
) -> dict[str, Any]:
    """Costruisce la guida operativa open-data per un ente con dati insufficienti.

    `entity_name`: nome del comune/ente. `n_datasets`: dataset valutabili trovati.
    `total_on_portal`: totale sul portale (può essere >0 ma sotto soglia/qualità).
    """
    name = (entity_name or "il Comune").strip()
    if n_datasets == 0:
        premessa = (
            f"Non sono stati trovati dataset aperti riconducibili a {name} sui cataloghi "
            "consultati. Non è un giudizio negativo: è il punto di partenza per costruire "
            "una politica di open data che crei valore per il territorio."
        )
    else:
        premessa = (
            f"Per {name} sono stati trovati solo {n_datasets} dataset valutabili "
            f"(su {total_on_portal} sul portale): troppo pochi per una valutazione "
            "affidabile. Ecco come ampliare e rafforzare il patrimonio open data."
        )

    passi = [
        {
            "titolo": "1. Nomina il Responsabile e definisci la governance",
            "descrizione": (
                "Individua il Responsabile per la Transizione al Digitale (RTD) e un "
                "referente open data. Inserisci gli open data negli obiettivi dell'ente."
            ),
            "riferimenti": [_REF_AGID],
        },
        {
            "titolo": "2. Censisci i dati che già produci",
            "descrizione": (
                "Mappa i dataset già esistenti (bilanci, tributi, mobilità, ambiente, "
                "servizi, contributi) anche se oggi in PDF o fogli di calcolo interni: "
                "sono la base del catalogo."
            ),
            "riferimenti": [_REF_HVD],
        },
        {
            "titolo": "3. Scegli una licenza aperta",
            "descrizione": (
                "Pubblica con licenza aperta (CC-BY 4.0 o IODL 2.0) così i dati sono "
                "legalmente riutilizzabili da cittadini, imprese e ricercatori."
            ),
            "riferimenti": [_REF_LICENZE],
        },
        {
            "titolo": "4. Descrivi i dati con metadati DCAT-AP_IT",
            "descrizione": (
                "Compila i metadati nel profilo nazionale DCAT-AP_IT (titolo, ente, "
                "tema, frequenza di aggiornamento, formato): rende i dataset trovabili "
                "e interoperabili."
            ),
            "riferimenti": [_REF_DCAT],
        },
        {
            "titolo": "5. Pubblica su un portale e fai harvesting su dati.gov.it",
            "descrizione": (
                "Pubblica su un portale CKAN (proprio o regionale) in formati aperti e "
                "machine-readable (CSV/JSON), poi fai indicizzare il catalogo sul "
                "Catalogo nazionale dati.gov.it."
            ),
            "riferimenti": [_REF_DATIGOV],
        },
        {
            "titolo": "6. Dai priorità ai dataset ad elevato valore (HVD)",
            "descrizione": (
                "Parti dalle categorie HVD (mobilità, geospaziale, ambiente, statistiche, "
                "società/imprese): generano più riuso e valore per il territorio."
            ),
            "riferimenti": [_REF_HVD],
        },
        {
            "titolo": "7. Aggiorna con regolarità e ascolta la domanda di riuso",
            "descrizione": (
                "Definisci una frequenza di aggiornamento e raccogli le richieste di dati "
                "da cittadini e imprese: l'open data è un servizio continuo, non un atto unico."
            ),
            "riferimenti": [_REF_AGID],
        },
    ]
    if open_license_ratio is not None and open_license_ratio < 0.5 and n_datasets > 0:
        passi.insert(2, {
            "titolo": "⚠ Verifica le licenze dei dataset esistenti",
            "descrizione": (
                "Meno della metà dei dataset trovati ha una licenza aperta riconosciuta: "
                "ripubblicali con CC-BY 4.0 o IODL 2.0 per renderli davvero riutilizzabili."
            ),
            "riferimenti": [_REF_LICENZE],
        })

    return {
        "titolo": f"Come avviare una politica di open data — {name}",
        "premessa": premessa,
        "passi": passi,
        "riferimenti": [_REF_AGID, _REF_DCAT, _REF_DATIGOV, _REF_HVD, _REF_LICENZE],
        "nota": (
            "Guida operativa a fini costruttivi: indica come valorizzare il patrimonio "
            "pubblico di dati, non esprime un giudizio sull'operato dell'ente."
        ),
    }
