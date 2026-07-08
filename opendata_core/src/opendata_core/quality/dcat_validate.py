"""Validatore DCAT-AP_IT + FAIR check + licenza (Punto 04 #52).

`validate_dcat(meta)` prende una scheda DCAT-AP_IT (l'output di `generate_dcat`
o un dataset DCAT incollato) e produce: segnalazioni puntuali sui campi
obbligatori mancanti/segnaposto, il controllo della licenza (aperta o no, con
suggerimento), un punteggio FAIR (Findable/Accessible/Interoperable/Reusable) e
un flag `valido`. Deterministico, senza dipendenze: misura ciò che la scheda
dichiara, non inventa nulla.
"""

from __future__ import annotations

from typing import Any

# Licenze aperte riconosciute (normalizzate: maiuscolo, senza spazi/underscore).
_OPEN_LICENSES = {
    "CC0", "CC0-1.0", "CC-BY-4.0", "CC-BY-3.0", "CC-BY-2.5", "CC-BY-SA-4.0",
    "CC-BY-SA-3.0", "IODL-2.0", "IODL-1.0", "ODBL-1.0", "ODBL", "ODC-BY-1.0",
    "ODC-BY", "PDDL-1.0", "PDDL",
}
_SUGGESTED_LICENSE = "CC-BY-4.0"

# Formati aperti e machine-readable (interoperabilità). PDF/DOC/XLS escapeno.
_OPEN_FORMATS = {"CSV", "TSV", "JSON", "GEOJSON", "XML", "RDF", "TTL", "N3", "PARQUET", "JSON-LD"}
_CLOSED_FORMATS = {"PDF", "DOC", "DOCX", "XLS", "XLSX", "PPT", "PPTX"}


def _norm_license(v: str) -> str:
    return v.strip().upper().replace("_", "-").replace(" ", "")


def _is_open_license(v: str) -> bool | None:
    """True/False se la licenza è aperta; None se non dichiarata/segnaposto."""
    if not _present(v):
        return None
    n = _norm_license(str(v))
    if "NC" in n.split("-") or "ND" in n.split("-"):  # NonCommercial / NoDerivatives
        return False
    if n in _OPEN_LICENSES:
        return True
    # CC-BY senza versione, IODL… → trattali come aperti se iniziano per prefissi noti
    if n.startswith(("CC-BY", "CC0", "IODL", "ODBL", "ODC-BY", "PDDL")):
        return "NC" not in n and "ND" not in n
    return False


def _present(v: Any) -> bool:
    """Campo valorizzato e non segnaposto ('<...>')."""
    if v is None:
        return False
    if isinstance(v, str):
        s = v.strip()
        return bool(s) and "<" not in s
    if isinstance(v, list):
        return any(_present(x) for x in v)
    if isinstance(v, dict):
        return any(_present(x) for x in v.values())
    return True


def _finding(livello: str, codice: str, messaggio: str, campo: str) -> dict[str, str]:
    return {"livello": livello, "codice": codice, "messaggio": messaggio, "campo": campo}


def _hvd_finding(meta: Any, campo: str) -> dict[str, str] | None:
    """Finding informativo se la scheda porta una stima HVD confidente (#102).

    Solo confidenza media/alta (una stima debole in validazione sarebbe rumore);
    livello `basso`, quindi non tocca mai `valido` né il punteggio FAIR.
    """
    hvd = meta.get("hvd_stimata") if isinstance(meta, dict) else None
    if not hvd or hvd.get("confidenza") not in ("media", "alta"):
        return None
    return _finding(
        "basso", "hvd_stimata",
        f"Il contenuto sembra un High-Value Dataset «{hvd['etichetta']}» "
        f"(confidenza {hvd['confidenza']}, stima euristica da verificare): il Reg. UE "
        f"2023/138 richiede per gli HVD licenza aperta, formato machine-readable e "
        f"disponibilità via API. Tema EU coerente: {hvd['tema_eu']}.",
        campo,
    )


def validate_dcat(meta: dict[str, Any]) -> dict[str, Any]:
    """Valida una scheda DCAT-AP_IT e calcola il punteggio FAIR."""
    dataset = meta.get("dataset", meta) if isinstance(meta, dict) else {}
    schema_campi = meta.get("schema_campi") if isinstance(meta, dict) else None
    dist = (dataset.get("dcat:distribution") or [{}])[0]

    title = dataset.get("dct:title")
    desc = dataset.get("dct:description")
    keyword = dataset.get("dcat:keyword")
    theme = dataset.get("dcat:theme")
    identifier = dataset.get("dct:identifier")
    publisher = (dataset.get("dct:publisher") or {}).get("foaf:name") if isinstance(dataset.get("dct:publisher"), dict) else dataset.get("dct:publisher")
    periodicity = dataset.get("dct:accrualPeriodicity")
    lic = dataset.get("dct:license") or dist.get("dct:license")
    dl_url = dist.get("dcat:downloadURL") or dist.get("dcat:accessURL")
    fmt = str(dist.get("dct:format") or "").upper()

    findings: list[dict[str, str]] = []

    # ── campi obbligatori / raccomandati ──
    if not _present(title):
        findings.append(_finding("alto", "title", "Manca il titolo (dct:title): obbligatorio.", "dct:title"))
    if not _present(desc):
        findings.append(_finding("alto", "description", "Manca la descrizione (dct:description): obbligatoria.", "dct:description"))
    if not _present(publisher):
        findings.append(_finding("medio", "publisher", "Manca l'ente titolare (dct:publisher).", "dct:publisher"))
    if not _present(theme):
        findings.append(_finding("medio", "theme", "Manca il tema EU (dcat:theme), es. GOVE/ECON/ENVI.", "dcat:theme"))
    if not _present(periodicity):
        findings.append(_finding("basso", "periodicity", "Manca la frequenza di aggiornamento (dct:accrualPeriodicity).", "dct:accrualPeriodicity"))
    if not _present(identifier):
        findings.append(_finding("basso", "identifier", "Manca l'identificativo (dct:identifier).", "dct:identifier"))
    if not _present(keyword):
        findings.append(_finding("basso", "keyword", "Mancano le parole chiave (dcat:keyword).", "dcat:keyword"))
    if not _present(dl_url):
        findings.append(_finding("medio", "download_url", "Manca l'URL della distribuzione (dcat:downloadURL).", "dcat:distribution"))

    # ── licenza ──
    aperta = _is_open_license(lic)
    if aperta is None:
        findings.append(_finding("alto", "license_missing",
                                 f"Manca la licenza (dct:license): senza licenza il dato non è riusabile. Suggerita {_SUGGESTED_LICENSE}.",
                                 "dct:license"))
    elif aperta is False:
        findings.append(_finding("alto", "license_closed",
                                 f"Licenza non aperta ({lic}): i dati aperti richiedono riuso libero (no NC/ND). Suggerita {_SUGGESTED_LICENSE}.",
                                 "dct:license"))

    # ── formato (interoperabilità) ──
    if fmt in _CLOSED_FORMATS:
        findings.append(_finding("medio", "format_closed",
                                 f"Formato non aperto ({fmt}): pubblica anche una versione CSV/JSON machine-readable.",
                                 "dct:format"))

    # ── stima HVD (#102, informativa) ──
    hvd_f = _hvd_finding(meta, "dcat:theme")
    if hvd_f:
        findings.append(hvd_f)

    # ── FAIR (0-100 per dimensione) ──
    findable = 20 * sum([_present(title), _present(desc), _present(keyword), _present(theme), _present(identifier)])
    accessible = (50 if _present(dl_url) else 0) + (25 if _present(fmt) else 0) + (25 if _present(dist.get("dcat:mediaType")) else 0)
    interop = (
        (60 if fmt in _OPEN_FORMATS else 0)
        + (20 if schema_campi else 0)
        + (20 if _present(dataset.get("@type")) else 0)
    )
    reusable = (
        (50 if aperta is True else 0)
        + (20 if _present(publisher) else 0)
        + (15 if _present(periodicity) else 0)
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
