"""Pacchetto pronto da pubblicare (Punto 04 #52, "Publish assistant").

`build_publish_package(...)` compone gli altri motori del Data Quality Lab in un
set di file pronti da caricare su un portale (CKAN o regionale): il dato, la
scheda DCAT-AP_IT, il file di licenza e un README con l'esito della validazione
FAIR e una checklist di pubblicazione. Restituisce il set di file (nome → testo):
lo zip lo crea il chiamante. Deterministico, senza dipendenze.
"""

from __future__ import annotations

import json
from typing import Any

from .dcat import generate_dcat
from .dcat_validate import validate_dcat

# Licenze aperte note → (nome esteso, URL). Per il file LICENSE.txt.
_LICENSE_INFO = {
    "CC-BY-4.0": ("Creative Commons Attribuzione 4.0 Internazionale (CC BY 4.0)",
                  "https://creativecommons.org/licenses/by/4.0/deed.it"),
    "CC0-1.0": ("Creative Commons Zero v1.0 — Pubblico dominio (CC0 1.0)",
                "https://creativecommons.org/publicdomain/zero/1.0/deed.it"),
    "CC-BY-SA-4.0": ("Creative Commons Attribuzione-Condividi allo stesso modo 4.0 (CC BY-SA 4.0)",
                     "https://creativecommons.org/licenses/by-sa/4.0/deed.it"),
    "IODL-2.0": ("Italian Open Data License 2.0 (IODL 2.0)",
                 "https://www.dati.gov.it/content/italian-open-data-license-v20"),
    "ODBL-1.0": ("Open Database License 1.0 (ODbL)",
                 "https://opendatacommons.org/licenses/odbl/1-0/"),
}
_SUGGESTED_LICENSE = "CC-BY-4.0"


def _norm(v: str) -> str:
    return v.strip().upper().replace("_", "-").replace(" ", "")


def _license_file(licenza: str | None) -> str:
    if not licenza or "<" in licenza:
        nome, url = _LICENSE_INFO[_SUGGESTED_LICENSE]
        return (
            "LICENZA NON ANCORA INDICATA\n\n"
            f"Per pubblicare come open data scegli una licenza aperta. Suggerita:\n"
            f"  {nome}\n  {url}\n\n"
            "Inserisci la licenza scelta nella scheda dei metadati (dct:license) prima di pubblicare.\n"
        )
    key = _norm(licenza)
    nome, url = _LICENSE_INFO.get(key, (licenza, ""))
    righe = [f"Licenza del dato: {nome}"]
    if url:
        righe.append(f"Testo completo: {url}")
    righe.append("")
    righe.append("Riutilizzo consentito alle condizioni della licenza indicata.")
    return "\n".join(righe) + "\n"


def _readme(dcat: dict[str, Any], validation: dict[str, Any], data_filename: str) -> str:
    ds = dcat.get("dataset", {})
    fair = validation.get("fair", {})
    righe: list[str] = [
        "PACCHETTO DI PUBBLICAZIONE OPEN DATA",
        "Generato dal Data Quality Lab di OpenData AI.",
        "",
        "CONTENUTO",
        f"  - {data_filename}            il dato, pulito e in formato standard",
        "  - metadati-dcat-ap_it.jsonld  la scheda dei metadati (DCAT-AP_IT)",
        "  - LICENSE.txt                 la licenza d'uso",
        "  - README.txt                  questo file",
        "",
        f"TITOLO: {ds.get('dct:title', '<da compilare>')}",
        "",
        "STATO VALIDAZIONE",
        f"  - Conformità DCAT-AP_IT: {'OK' if validation.get('valido') else 'da completare'}",
        f"  - Punteggio FAIR: {fair.get('overall', 0)}/100 "
        f"(Trovabile {fair.get('findable', 0)}, Accessibile {fair.get('accessible', 0)}, "
        f"Interoperabile {fair.get('interoperable', 0)}, Riutilizzabile {fair.get('reusable', 0)})",
    ]
    hvd = dcat.get("hvd_stimata")
    if hvd:
        righe += [
            "",
            "CATEGORIA HVD (STIMATA)",
            f"  {hvd['etichetta']} — confidenza {hvd['confidenza']} (stima euristica, da verificare)",
            "  Gli High-Value Dataset (Reg. UE 2023/138) richiedono licenza aperta,",
            "  formato machine-readable e disponibilità via API.",
        ]
    findings = validation.get("findings", [])
    if findings:
        righe.append("")
        righe.append("DA SISTEMARE PRIMA DI PUBBLICARE")
        for f in findings:
            righe.append(f"  [{f['livello']}] {f['messaggio']}")
    righe += [
        "",
        "COME PUBBLICARE (CKAN / portale regionale)",
        "  1. Crea un nuovo dataset sul portale del tuo ente.",
        "  2. Compila i metadati usando metadati-dcat-ap_it.jsonld.",
        f"  3. Carica {data_filename} come risorsa e imposta la licenza.",
        "  4. Verifica che il dataset risulti nel catalogo nazionale (dati.gov.it).",
    ]
    return "\n".join(righe) + "\n"


def build_publish_package(
    profile: dict[str, Any],
    *,
    data_filename: str,
    data_content: str,
    titolo: str | None = None,
    descrizione: str | None = None,
    licenza: str | None = None,
    ente: str | None = None,
    tema: str | None = None,
    frequenza: str | None = None,
    url: str | None = None,
) -> dict[str, Any]:
    """Compone il set di file del pacchetto + validazione + metadati.

    Returns:
        {"files": {nome: testo}, "validazione": ..., "metadata": ...}.
    """
    dcat = generate_dcat(
        profile, titolo=titolo, descrizione=descrizione, licenza=licenza,
        ente=ente, tema=tema, frequenza=frequenza, url=url,
    )
    validation = validate_dcat(dcat)
    files = {
        data_filename: data_content,
        "metadati-dcat-ap_it.jsonld": json.dumps(dcat, ensure_ascii=False, indent=2),
        "LICENSE.txt": _license_file(licenza),
        "README.txt": _readme(dcat, validation, data_filename),
    }
    return {"files": files, "validazione": validation, "metadata": dcat}
