"""Suggerimenti di arricchimento da un profilo CSV (Punto 01 #49, ultima voce).

`advise_enrichment(profile)` legge il profilo di `profile_csv` (nomi colonna,
tipo, cardinalità, esempi) e suggerisce — in modo deterministico, solo su ciò
che si misura sul file — tre tipi di arricchimento tipici dell'open data
italiano: join con i codici ISTAT dei comuni, geocoding degli indirizzi in
coordinate mappabili, vocabolari controllati per le colonne categoriali a
testo libero. Nessuna chiamata di rete: solo euristiche sui nomi/valori delle
colonne. Niente LLM, niente dipendenze.
"""

from __future__ import annotations

import re
from typing import Any

# nomi colonna che indicano un luogo testuale non ancora codificato
_RE_COMUNE = re.compile(r"(^|_)(comune|citt[aà]|municipio)(_|$)", re.IGNORECASE)
_RE_PROVINCIA = re.compile(r"(^|_)(provincia|prov)(_|$)", re.IGNORECASE)
_RE_REGIONE = re.compile(r"(^|_)(regione)(_|$)", re.IGNORECASE)
_RE_LUOGO = re.compile(f"{_RE_COMUNE.pattern}|{_RE_PROVINCIA.pattern}|{_RE_REGIONE.pattern}", re.IGNORECASE)

# colonna già codificata (ISTAT/catastale): non serve arricchimento
_RE_GIA_CODIFICATA = re.compile(r"(^|_)(istat|catastale|cod[_]?istat)(_|$)", re.IGNORECASE)

# nomi colonna che indicano un indirizzo da geocodificare
_RE_INDIRIZZO = re.compile(r"(^|_)(indirizzo|via|strada|address|civico)(_|$)", re.IGNORECASE)
_RE_CAP = re.compile(r"(^|_)(cap|zip)(_|$)", re.IGNORECASE)

# colonna già coordinata (vedi geoconvert._LAT_NAMES/_LON_NAMES)
_RE_COORD = re.compile(r"(^|_)(lat|lon|lng|latitud[ei]|longitud[ei])(_|$)", re.IGNORECASE)

# colonna categoriale a "bassa" cardinalità: candidata a vocabolario controllato
_MIN_CAT_DISTINCT = 2
_MAX_CAT_DISTINCT = 30


def _suggerimento(codice: str, titolo: str, dettaglio: str, colonne: list[str]) -> dict[str, Any]:
    return {"codice": codice, "titolo": titolo, "dettaglio": dettaglio, "colonne": colonne}


def _colonne_luogo(cols: list[dict[str, Any]]) -> list[str]:
    """Colonne testuali di luogo, solo se il file non ha già un codice ISTAT."""
    if any(_RE_GIA_CODIFICATA.search(str(c.get("nome", ""))) for c in cols):
        return []
    return [
        c["nome"] for c in cols
        if c.get("tipo") == "testo" and _RE_LUOGO.search(str(c.get("nome", "")))
    ]


def _colonne_indirizzo(cols: list[dict[str, Any]]) -> list[str]:
    return [
        c["nome"] for c in cols
        if c.get("tipo") == "testo" and _RE_INDIRIZZO.search(str(c.get("nome", "")))
    ]


def _ha_coordinate(cols: list[dict[str, Any]]) -> bool:
    nomi = [str(c.get("nome", "")) for c in cols]
    return any(_RE_COORD.search(n) for n in nomi)


def _colonne_vocabolario(cols: list[dict[str, Any]], escludi: set[str]) -> list[dict[str, Any]]:
    out = []
    for c in cols:
        nome = str(c.get("nome", ""))
        if nome in escludi:
            continue
        if c.get("tipo") != "testo":
            continue
        distinti = int(c.get("distinti") or 0)
        if _MIN_CAT_DISTINCT <= distinti <= _MAX_CAT_DISTINCT:
            out.append(c)
    return out


def advise_enrichment(profile: dict[str, Any]) -> dict[str, Any]:
    """Suggerimenti di arricchimento dal profilo di un CSV.

    Args:
        profile: output di `profile_csv` (serve `colonne_profilo`).

    Returns:
        {"arricchimenti": [...]}, uno per tipo di suggerimento rilevato
        (join_istat, geocoding, vocabolario_controllato). Lista vuota se il
        file non presenta colonne candidate.
    """
    cols = profile.get("colonne_profilo") or []

    arricchimenti: list[dict[str, Any]] = []

    luogo_cols = _colonne_luogo(cols)
    if luogo_cols:
        arricchimenti.append(_suggerimento(
            "join_istat",
            "Aggiungi il codice ISTAT del comune",
            "Le colonne " + ", ".join(f"«{c}»" for c in luogo_cols)
            + " contengono nomi di luogo in chiaro: un join con l'anagrafica ISTAT dei comuni "
            "(codice a 6 cifre) rende il dato univoco e facilmente incrociabile con altre fonti "
            "open data (niente ambiguità tra comuni omonimi o varianti di scrittura).",
            luogo_cols,
        ))

    indirizzo_cols = _colonne_indirizzo(cols)
    if indirizzo_cols and not _ha_coordinate(cols):
        arricchimenti.append(_suggerimento(
            "geocoding",
            "Geocodifica gli indirizzi in coordinate",
            "Le colonne " + ", ".join(f"«{c}»" for c in indirizzo_cols)
            + " sono indirizzi testuali senza colonne di latitudine/longitudine: geocodificarli "
            "(es. via Nominatim/OSM) aggiunge coordinate mappabili e permette di visualizzare il "
            "dato su una mappa o incrociarlo con altri dataset geografici.",
            indirizzo_cols,
        ))

    vocab_cols = _colonne_vocabolario(cols, escludi=set(luogo_cols) | set(indirizzo_cols))
    if vocab_cols:
        nomi = [c["nome"] for c in vocab_cols]
        arricchimenti.append(_suggerimento(
            "vocabolario_controllato",
            "Standardizza le colonne categoriali con un vocabolario controllato",
            "Le colonne " + ", ".join(f"«{n}»" for n in nomi)
            + " hanno pochi valori distinti ma sono a testo libero: un vocabolario controllato "
            "(codelist) elimina varianti di scrittura e refusi, e rende il dato confrontabile con "
            "altri dataset che usano la stessa codifica.",
            nomi,
        ))

    return {"arricchimenti": arricchimenti}
