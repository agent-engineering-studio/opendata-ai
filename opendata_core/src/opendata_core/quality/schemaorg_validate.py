"""Validatore schema.org/Dataset + FAIR check + licenza (Punto 04 #52).

`validate_schema_org(meta)` è il gemello di `dcat_validate.py::validate_dcat`
ma per una scheda **schema.org/Dataset** (l'output di `generate_schema_org` o
un JSON-LD incollato): stessi criteri — campi obbligatori/raccomandati,
licenza aperta o no, punteggio FAIR — sullo stesso vocabolario che legge
Google Dataset Search. Riusa le euristiche di licenza/formato di
`dcat_validate` (stesse regole, vocabolario diverso). Deterministico.
"""

from __future__ import annotations

from typing import Any

from .dcat_validate import (
    _CLOSED_FORMATS,
    _OPEN_FORMATS,
    _SUGGESTED_LICENSE,
    _finding,
    _is_open_license,
    _present,
)


def validate_schema_org(meta: dict[str, Any]) -> dict[str, Any]:
    """Valida una scheda schema.org/Dataset e calcola il punteggio FAIR."""
    dataset = meta.get("dataset", meta) if isinstance(meta, dict) else {}
    schema_campi = meta.get("schema_campi") if isinstance(meta, dict) else None
    dist = (dataset.get("distribution") or [{}])[0]

    name = dataset.get("name")
    desc = dataset.get("description")
    keywords = dataset.get("keywords")
    about = dataset.get("about")
    identifier = dataset.get("identifier")
    creator = dataset.get("creator") or dataset.get("publisher")
    creator_name = creator.get("name") if isinstance(creator, dict) else creator
    temporal = dataset.get("temporalCoverage")
    lic = dataset.get("license") or dist.get("license")
    dl_url = dist.get("contentUrl")
    fmt_raw = str(dist.get("encodingFormat") or "")
    fmt = fmt_raw.split("/")[-1].upper() if "/" in fmt_raw else fmt_raw.upper()

    findings: list[dict[str, str]] = []

    if not _present(name):
        findings.append(_finding("alto", "name", "Manca il nome (name): obbligatorio.", "name"))
    if not _present(desc):
        findings.append(_finding("alto", "description", "Manca la descrizione (description): obbligatoria.", "description"))
    if not _present(creator_name):
        findings.append(_finding("medio", "creator", "Manca l'editore (creator/publisher).", "creator"))
    if not _present(about):
        findings.append(_finding("medio", "about", "Manca l'argomento (about).", "about"))
    if not _present(temporal):
        findings.append(_finding("basso", "temporal_coverage", "Manca la copertura temporale (temporalCoverage).", "temporalCoverage"))
    if not _present(identifier):
        findings.append(_finding("basso", "identifier", "Manca l'identificativo (identifier).", "identifier"))
    if not _present(keywords):
        findings.append(_finding("basso", "keywords", "Mancano le parole chiave (keywords).", "keywords"))
    if not _present(dl_url):
        findings.append(_finding("medio", "download_url", "Manca l'URL della distribuzione (distribution.contentUrl).", "distribution"))

    aperta = _is_open_license(lic) if lic else None
    if aperta is None:
        findings.append(_finding("alto", "license_missing",
                                 f"Manca la licenza (license): senza licenza il dato non è riusabile. Suggerita {_SUGGESTED_LICENSE}.",
                                 "license"))
    elif aperta is False:
        findings.append(_finding("alto", "license_closed",
                                 f"Licenza non aperta ({lic}): i dati aperti richiedono riuso libero (no NC/ND). Suggerita {_SUGGESTED_LICENSE}.",
                                 "license"))

    if fmt in _CLOSED_FORMATS:
        findings.append(_finding("medio", "format_closed",
                                 f"Formato non aperto ({fmt}): pubblica anche una versione CSV/JSON machine-readable.",
                                 "encodingFormat"))

    findable = 20 * sum([_present(name), _present(desc), _present(keywords), _present(about), _present(identifier)])
    accessible = (50 if _present(dl_url) else 0) + (25 if fmt else 0) + (25 if _present(dist.get("encodingFormat")) else 0)
    interop = (
        (60 if fmt in _OPEN_FORMATS else 0)
        + (20 if schema_campi else 0)
        + (20 if _present(dataset.get("@type")) else 0)
    )
    reusable = (
        (50 if aperta is True else 0)
        + (20 if _present(creator_name) else 0)
        + (15 if _present(temporal) else 0)
        + (15 if _present(desc) else 0)
    )
    fair = {
        "findable": findable,
        "accessible": accessible,
        "interoperable": interop,
        "reusable": reusable,
        "overall": round((findable + accessible + interop + reusable) / 4),
    }

    valido = not any(f["livello"] == "alto" for f in findings)
    return {
        "valido": valido,
        "findings": findings,
        "licenza": {
            "dichiarata": lic if _present(lic) else None,
            "aperta": aperta,
            "suggerita": None if aperta is True else _SUGGESTED_LICENSE,
        },
        "fair": fair,
    }
