"""Stima High-Value Dataset a livello di singolo file (Punto 04 #52 → #102).

`advise_hvd(profile)` stima se il file rientra in una delle 6 categorie
**High-Value Dataset** UE (Reg. 2023/138) — geospaziale, osservazione della
Terra/ambiente, meteo, statistici, imprese/proprietà, mobilità — con la stessa
tabella di keyword del match a livello di ente (`maturity.hvd.HVD_KEYWORDS`),
applicata però a ciò che si vede nel singolo file: nomi di colonna, titolo,
nome del file. A differenza del match di ente (prima categoria e basta), qui si
valutano TUTTE le categorie e ogni stima porta una **confidenza** esplicita con
gli indizi che l'hanno prodotta: euristica dichiaratamente approssimata, mai un
verdetto secco. Deterministico, nessuna rete, nessuna dipendenza.
"""

from __future__ import annotations

import re
from typing import Any

from ..maturity.coverage import HVD_LABELS
from ..maturity.hvd import HVD_KEYWORDS, _matches

# Tema EU (vocabolario data-theme) coerente con ciascuna categoria HVD: mostrato
# come suggerimento etichettato per `dcat:theme`, mai compilato in automatico.
_EU_THEME = {
    "geospatial": "REGI",
    "earth_observation_environment": "ENVI",
    "meteorological": "ENVI",
    "statistics": "SOCI",
    "companies_ownership": "ECON",
    "mobility": "TRAN",
}

# Colonne di coordinate: indizio strutturale per la categoria geospaziale
# (stessa famiglia di nomi di enrich/geoconvert).
_RE_COORD = re.compile(r"(^|_)(lat|lon|lng|latitud[ei]|longitud[ei])(_|$)", re.IGNORECASE)


def _confidenza(n_indizi: int) -> str:
    # Volutamente prudente: un solo indizio resta "bassa" — le keyword sono
    # tarate su titoli/descrizioni e i nomi di colonna sono corti e criptici.
    if n_indizi >= 3:
        return "alta"
    if n_indizi == 2:
        return "media"
    return "bassa"


def _filename_from_url(url: str) -> str:
    """Ultimo segmento del path, senza query né estensione."""
    path = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    name = path.rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[0] if "." in name else name


def _blob(profile: dict[str, Any], titolo: str | None, url: str | None) -> str:
    """Testo su cui cercare le keyword: nomi colonna + titolo + nome file."""
    parti: list[str] = [str(c.get("nome", "")) for c in profile.get("colonne_profilo") or []]
    if titolo:
        parti.append(titolo)
    if url:
        parti.append(_filename_from_url(url))
    # separatori tipici dei nomi macchina → spazi, così "piste_ciclabili"
    # combacia con la keyword multi-parola "piste ciclabili"
    return re.sub(r"[_\-./]+", " ", " ; ".join(parti).lower())


def advise_hvd(
    profile: dict[str, Any],
    *,
    titolo: str | None = None,
    url: str | None = None,
) -> dict[str, Any]:
    """Stima le categorie HVD di un file profilato (CSV o GeoJSON).

    Args:
        profile: output di `profile_csv` o `profile_geojson`.
        titolo: titolo editoriale del dataset, se noto (migliora la stima).
        url: URL/nome del file, se noto (il nome file è spesso parlante).

    Returns:
        {"categorie": [{codice, etichetta, confidenza, indizi, tema_eu}, ...],
         "nota": str} — categorie ordinate per evidenza, lista vuota quando non
        emerge nulla. La confidenza è dichiarata, mai un verdetto secco.
    """
    is_geo = (profile.get("format") or "").upper() == "GEOJSON"
    blob = _blob(profile, titolo, url)

    per_categoria: dict[str, list[str]] = {}
    for categoria, keywords in HVD_KEYWORDS:
        indizi = [kw for kw in keywords if _matches(blob, kw)]
        if indizi:
            per_categoria[categoria] = [f"parola «{kw}»" for kw in indizi]

    # indizi strutturali (non dipendono dalle parole)
    if is_geo:
        # un GeoJSON è per natura un dato geografico: confidenza alta diretta
        per_categoria.setdefault("geospatial", []).insert(
            0, "il file è un GeoJSON: dato geografico per natura"
        )
    else:
        coord = [
            str(c.get("nome", "")) for c in profile.get("colonne_profilo") or []
            if _RE_COORD.search(str(c.get("nome", "")))
        ]
        if coord:
            per_categoria.setdefault("geospatial", []).append(
                "colonne di coordinate (" + ", ".join(coord) + ")"
            )

    priorita = {cat: i for i, (cat, _) in enumerate(HVD_KEYWORDS)}
    categorie: list[dict[str, Any]] = []
    for categoria, indizi in per_categoria.items():
        conf = "alta" if is_geo and categoria == "geospatial" else _confidenza(len(indizi))
        categorie.append({
            "codice": categoria,
            "etichetta": HVD_LABELS.get(categoria, categoria),
            "confidenza": conf,
            "indizi": indizi,
            "tema_eu": _EU_THEME[categoria],
        })
    categorie.sort(key=lambda c: (-len(c["indizi"]), priorita.get(c["codice"], 99)))

    nota = (
        "Stima euristica su nomi di colonna, titolo e nome del file: è un'indicazione "
        "da verificare, non un verdetto. Gli High-Value Dataset (Reg. UE 2023/138) "
        "hanno obblighi specifici: licenza aperta, formato machine-readable e "
        "disponibilità via API."
        if categorie else
        "Nessuna categoria HVD evidente dai nomi di colonna, dal titolo o dal nome del "
        "file: la stima è euristica, un dataset può essere HVD anche senza che i suoi "
        "nomi di colonna lo rivelino."
    )
    return {"categorie": categorie, "nota": nota}
