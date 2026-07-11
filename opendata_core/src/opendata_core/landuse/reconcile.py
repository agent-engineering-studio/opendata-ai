"""Riconciliazione OSM ↔ stato reale del suolo — motore PURO (#127, Parte V Fase 1).

Per ogni poligono candidato (vuoto urbano / area dismessa enumerata da
`osm.overpass_candidate_areas`) produce il **record riconciliato** §4.5: confronta
il tag OSM con le fonti ground-truth **oggi disponibili** (IdroGEO PAI a scala
comunale + progetti OpenCoesione) e classifica stato del suolo, causa di abbandono
e azione consigliata.

Principio guida (#127): ogni fonte mancante **degrada la confidenza, non blocca il
report**. I nodi dell'albero §4.3 non risolvibili con le fonti correnti
(edificato/impermeabilizzato → Copernicus/ortofoto, destinazione PUG, catasto,
proprietà) restano `"da verificare"` con una voce esplicita in `caveat`.

Motore puro come gli altri di `opendata_core`: nessun FastAPI/LLM/I/O di rete —
riceve i dati già recuperati dal chiamante (la lente backend).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from ..ispra.models import LandCoverInfo, RiskIndicators

Confidenza = Literal["Alta", "Media", "Bassa"]
Classificazione = Literal["VINCOLATO", "DISMESSO", "LIBERO", "SPAZIO_PUBBLICO", "DA_VERIFICARE"]

DA_VERIFICARE = "da verificare"

# Fonti ground-truth NON ancora nel codebase (§4, fasi successive): ogni campo che
# le richiederebbe resta "da verificare" con questo caveat.
_CAVEAT_USO_REALE = "uso reale del suolo non verificabile: mancano ortofoto/NDVI e Copernicus (Fase 2, #128)"
_CAVEAT_PUG = "destinazione urbanistica non interrogabile: il PUG non è ancora dato aperto (Fase 3, #129)"
_CAVEAT_CATASTO = "dati catastali/proprietà non disponibili come fonte aperta"
_CAVEAT_IDROGEO_COMUNALE = (
    "vincolo idrogeologico a scala COMUNALE (IdroGEO PAI): non è l'intersezione "
    "geometrica del singolo poligono — da verificare puntualmente"
)
_CAVEAT_NO_IDROGEO = "vincolo idrogeologico non valutato: indicatori IdroGEO PAI non disponibili"
_CAVEAT_CLC_SCALA = (
    "copertura del suolo da Corine Land Cover (scala nazionale, unità minima ~25 ha): "
    "indicativa per micro-poligoni"
)

# `kind` (derivato dai tag OSM in `overpass_candidate_areas`) → segnale di dismissione.
_DISMESSO_HINT = ("brownfield", "disused", "abandoned", "ruins", "ex-militare", "ruderi")
_CAUSA_ABBANDONO = {
    "brownfield": "area produttiva/industriale dismessa (da bonificare)",
    "ruins": "edificato in stato di rovina",
    "ex-militare": "ex uso militare cessato",
    "military": "ex uso militare cessato",
    "railway": "ex sedime ferroviario dismesso",
}


class SoilRecord(BaseModel):
    """Record riconciliato per poligono (schema §4.5).

    `confidenza` è esplicita e `caveat` elenca le fonti mancanti che tengono
    alcuni campi a `"da verificare"`. NON è un giudizio bloccante: è la base del
    gate avvisante (WARN) e del futuro export (Fase 4)."""

    id_geometria: str
    tag_osm: str
    uso_reale: str = DA_VERIFICARE
    destinazione_pug: str = DA_VERIFICARE
    catasto: str = DA_VERIFICARE
    proprieta: str = DA_VERIFICARE
    stato_attivita: str = DA_VERIFICARE
    vincoli: str = DA_VERIFICARE
    classificazione: Classificazione = "DA_VERIFICARE"
    discrepanza_osm: str = DA_VERIFICARE
    causa_abbandono: str = DA_VERIFICARE
    azione_consigliata: str = DA_VERIFICARE
    confidenza: Confidenza = "Bassa"
    caveat: list[str] = []
    # Passthrough utile a lente/UI (non parte dello schema §4.5, non influisce sui gate).
    nome: str | None = None
    url: str | None = None
    area_mq: int | None = None


def _vincolo_da_idrogeo(idrogeo: RiskIndicators | None) -> str | None:
    """Descrizione del vincolo idrogeologico comunale, o None se non valutabile.

    Usa l'aggregato frane P3-P4 (pericolosità elevata/molto elevata, spec 07) e la
    presenza di classi idrauliche con superficie esposta."""
    if idrogeo is None:
        return None
    parti: list[str] = []
    p3p4 = idrogeo.frane_p3p4
    if p3p4 is not None and (p3p4.area_pct or p3p4.area_kmq):
        pct = f"{round(p3p4.area_pct, 1)}%" if p3p4.area_pct is not None else "area non nulla"
        parti.append(f"frane P3-P4 {pct} del territorio comunale")
    idro = [s for s in idrogeo.idraulica if (s.area_pct or s.area_kmq)]
    if idro:
        classi = ", ".join(sorted({s.classe.upper() for s in idro}))
        parti.append(f"pericolosità idraulica ({classi})")
    if not parti:
        return None
    return "; ".join(parti)


def _causa_abbandono(kind: str) -> str:
    k = kind.lower()
    for hint, causa in _CAUSA_ABBANDONO.items():
        if hint in k:
            return causa
    if any(h in k for h in _DISMESSO_HINT):
        return "uso cessato (tipologia dismessa non ulteriormente qualificata dal tag OSM)"
    return DA_VERIFICARE


def reconcile_polygon(
    *,
    osm_feature: dict[str, Any],
    idrogeo: RiskIndicators | None = None,
    investimenti: list[dict[str, Any]] | None = None,
    land_cover: LandCoverInfo | None = None,
) -> SoilRecord:
    """Costruisce il `SoilRecord` §4.5 per un poligono candidato.

    Args:
        osm_feature: area candidata di `osm.overpass_candidate_areas`
            (`{osm_type, osm_id, name, kind, area_mq, url, ...}`).
        idrogeo: indicatori IdroGEO PAI del comune (scala comunale), o None.
        investimenti: progetti OpenCoesione nel comune (segnale di attività/riuso),
            o None/vuoto.
        land_cover: copertura del suolo puntuale (Corine Land Cover ISPRA, #128
            Fase 2c), o None. Risolve il nodo "edificato/impermeabilizzato" §4.3.

    Regola di confidenza (§4.5): **Alta** solo se ≥2 fonti concordano; **Bassa** se
    la sola evidenza è il tag OSM; **Media** se 2 fonti ma con un segnale a scala
    comunale o una discrepanza. Ogni campo non risolvibile → `"da verificare"` +
    caveat.
    """
    kind = str(osm_feature.get("kind") or "area").strip()
    otype = osm_feature.get("osm_type", "way")
    oid = osm_feature.get("osm_id")
    id_geometria = f"{otype}/{oid}"

    caveat: list[str] = [_CAVEAT_USO_REALE, _CAVEAT_PUG, _CAVEAT_CATASTO]
    fonti = 1  # il tag OSM è sempre una fonte
    dismesso = any(h in kind.lower() for h in _DISMESSO_HINT)

    # ── copertura del suolo puntuale (Corine Land Cover ISPRA, #128 Fase 2c) ──
    uso_reale = DA_VERIFICARE
    impermeabilizzato: bool | None = None
    if land_cover is not None:
        uso_reale = f"{land_cover.descrizione} (CLC {land_cover.clc_code})"
        impermeabilizzato = land_cover.impermeabilizzato
        caveat.remove(_CAVEAT_USO_REALE)  # nodo §4.3 risolto: non più "da verificare"
        caveat.append(_CAVEAT_CLC_SCALA)
        fonti += 1

    # ── vincolo idrogeologico (IdroGEO PAI, comune-level) ──
    vincolo = _vincolo_da_idrogeo(idrogeo)
    if vincolo is not None:
        vincoli = f"VINCOLATO — {vincolo}"
        caveat.append(_CAVEAT_IDROGEO_COMUNALE)
        fonti += 1
    else:
        vincoli = DA_VERIFICARE
        caveat.append(_CAVEAT_NO_IDROGEO)

    # ── attività / riuso in corso (progetti OpenCoesione nel comune) ──
    n_progetti = len(investimenti or [])
    attivita_presente = n_progetti > 0
    if attivita_presente:
        stato_attivita = f"attività/riuso in corso: {n_progetti} progetto/i OpenCoesione nel comune"
        fonti += 1
    elif dismesso:
        stato_attivita = "inattivo/dismesso (dal tag OSM)"
    else:
        stato_attivita = DA_VERIFICARE

    # ── classificazione (albero §4.3, nodi attivabili) ──
    if vincolo is not None:
        classificazione: Classificazione = "VINCOLATO"
    elif dismesso:
        classificazione = "DISMESSO"
    elif "greenfield" in kind.lower():
        classificazione = "LIBERO"
    elif kind.lower() in ("square", "parking"):
        classificazione = "SPAZIO_PUBBLICO"
    else:
        classificazione = "DA_VERIFICARE"

    # ── discrepanza OSM ↔ realtà (usa la copertura del suolo quando disponibile) ──
    contraddizione = False
    if classificazione == "LIBERO" and impermeabilizzato:
        discrepanza = (
            "OSM segna l'area come libera/edificabile ma la copertura del suolo risulta "
            "impermeabilizzata (Corine Land Cover, superfici artificiali)"
        )
        contraddizione = True
    elif dismesso and attivita_presente:
        discrepanza = (
            "possibile disallineamento: OSM segna l'area come dismessa ma risultano "
            "progetti attivi nel comune — verificare se il riuso ha già interessato il poligono"
        )
        contraddizione = True
    elif dismesso and impermeabilizzato is False:
        discrepanza = (
            "area dismessa ma copertura del suolo non artificiale: possibile "
            "rinaturalizzazione (o unità CLC troppo grande), verificare sul campo"
        )
        contraddizione = True
    elif land_cover is not None:
        discrepanza = f"tag OSM coerente con la copertura del suolo rilevata ({land_cover.descrizione})"
    else:
        discrepanza = "non valutabile senza confronto ortofoto/Copernicus (Fase 2)"

    # ── azione consigliata ──
    azione = {
        "VINCOLATO": "verificare puntualmente il vincolo PAI sul poligono prima di ogni ipotesi di riuso",
        "DISMESSO": "candidabile a rigenerazione/riuso: verificare proprietà, destinazione PUG e bonifica",
        "LIBERO": "verificare la destinazione urbanistica prima di considerarla edificabile",
        "SPAZIO_PUBBLICO": "valutare riqualificazione/uso polifunzionale dello spazio",
        "DA_VERIFICARE": "sopralluogo e verifica documentale per attribuire lo stato del suolo",
    }[classificazione]

    # ── confidenza (§4.5): ≥2 fonti concordi → Alta; solo tag → Bassa ──
    if fonti <= 1:
        confidenza: Confidenza = "Bassa"
    elif contraddizione:
        confidenza = "Media"
    else:
        confidenza = "Alta"

    return SoilRecord(
        id_geometria=id_geometria,
        tag_osm=kind,
        uso_reale=uso_reale,
        stato_attivita=stato_attivita,
        vincoli=vincoli,
        classificazione=classificazione,
        discrepanza_osm=discrepanza,
        causa_abbandono=_causa_abbandono(kind) if dismesso else DA_VERIFICARE,
        azione_consigliata=azione,
        confidenza=confidenza,
        caveat=caveat,
        nome=osm_feature.get("name"),
        url=osm_feature.get("url"),
        area_mq=osm_feature.get("area_mq"),
    )
