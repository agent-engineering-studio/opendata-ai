"""Aggregatore "Programma Evidence-Based" — scheda SWOT + proposte per la PA.

Riusa il fan-out esistente con un aggregatore dedicato (stesso meccanismo di
`synth.build_aggregator`, contratto di output diverso): i partecipanti
raccolgono evidenze sul comune, un agente tool-less (`programma_agent`) le
trasforma nel JSON strutturato della scheda, e i guardrail deterministici di
`guardrails.validate_programma` scartano ogni claim senza fonte risolvibile.

Principio non negoziabile (spec 04): dato → evidenza → proposta. L'output è
analisi verificabile, non propaganda.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Literal

from agent_framework import Agent
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from .guardrails import validate_programma
from .parsing import Resource, parse_agent_reply
from .sources import resolve_source_url
from .synth import (
    _capture_tool_resources,
    _executor_id,
    _extract_text_from_result,
    _is_placeholder_url,
    _normalise_source_tag,
)

log = logging.getLogger("orchestrator.programma")

FonteEvidenza = Literal[
    "istat", "opencoesione", "ckan", "eurostat", "oecd", "osm", "ispra", "kg", "web"
]

SWOT_KEYS = ("forze", "debolezze", "opportunita", "minacce")


# ─────────────────────────── contratto dati (spec 04 §6) ───────────────────


class Evidenza(BaseModel):
    # Tag della fonte (istat, opencoesione, …). Tipato str e normalizzato, non
    # Literal: i modelli piccoli producono typo ("ospr") e una voce malformata
    # non deve invalidare la scheda — il guardrail vero è l'URL risolvibile.
    fonte: str
    url: str  # risolvibile, copiata VERBATIM dalle risorse raccolte
    dettaglio: str  # cosa dice il dato (no interpretazione)
    # Tier (spec 09): "certificato" = dato aperto ufficiale; "documentale" =
    # fatto da documenti comunali ingeriti nel KG (delibere, piani, bilanci).
    # DERIVATO dalla fonte, mai dall'LLM: kg → documentale, il resto certificato.
    tier: Literal["certificato", "documentale"] = "certificato"
    # Tipo di fonte per il marketing territoriale (spec 10): "dato_locale" =
    # premessa verificabile dalle fonti locali; "ispirazione_esterna" = spunto
    # da una ricerca web (iniziativa di un altro ente). DERIVATO dalla fonte,
    # mai dall'LLM: web → ispirazione_esterna, il resto dato_locale. Il guardrail
    # marketing pretende ALMENO una premessa locale + un'ispirazione esterna.
    fonte_tipo: Literal["dato_locale", "ispirazione_esterna"] = "dato_locale"

    @field_validator("fonte")
    @classmethod
    def _normalise_fonte(cls, v: str) -> str:
        # i modelli piccoli copiano il tag con la decorazione ("[opencoesione]")
        return v.strip().strip("[]()").strip().lower()

    @model_validator(mode="after")
    def _derive_tier(self) -> "Evidenza":
        self.tier = "documentale" if self.fonte == "kg" else "certificato"
        self.fonte_tipo = "ispirazione_esterna" if self.fonte == "web" else "dato_locale"
        return self


class VoceSwot(BaseModel):
    testo: str
    evidenze: list[Evidenza]  # ≥1 obbligatoria (i guardrail scartano le orfane)


class Fattibilita(BaseModel):
    livello: Literal["alta", "media", "bassa", "da_verificare"]
    motivazione: str
    spend_ratio_storico: float | None = None  # da OpenCoesione


class Finanziamento(BaseModel):
    linea: str
    fonte_url: str
    stato: str | None = None


class Proposta(BaseModel):
    titolo: str
    descrizione: str
    evidenze: list[Evidenza]  # ≥1 obbligatoria
    finanziamento: Finanziamento | None = None
    fattibilita: Fattibilita
    # Modalità "idee" (Pezzo 8): da quale scarto nasce l'idea. Obbligatorio in
    # modalità idee (i guardrail scartano le proposte senza generatore valido);
    # assente in modalità scheda. str normalizzato, non Literal (lezione del
    # campo `fonte`: un typo non deve invalidare il parse — lo gestisce il
    # guardrail).
    generatore: str | None = None
    # Lente tematica del marketing territoriale (Pezzo 10): turismo_cultura,
    # viabilita_mobilita, sicurezza_vivibilita, attrattivita_brand. Usata SOLO
    # in modalità "marketing" per raggruppare gli spunti nella sezione dedicata;
    # None nelle altre modalità. str normalizzato (come `generatore`).
    lente: str | None = None

    @field_validator("generatore")
    @classmethod
    def _normalise_generatore(cls, v: str | None) -> str | None:
        return v.strip().lower() if isinstance(v, str) and v.strip() else None

    @field_validator("lente")
    @classmethod
    def _normalise_lente(cls, v: str | None) -> str | None:
        return v.strip().lower() if isinstance(v, str) and v.strip() else None


class ProgrammaRequest(BaseModel):
    cod_comune: str  # codice ISTAT, es. "072006"
    # Nome del comune: gli specialisti che geocodificano (OSM) o cercano per
    # testo (CKAN) non sanno risolvere il codice ISTAT — senza nome l'agente
    # OSM finisce a geocodificare "zona industriale, Italia" (visto in smoke).
    comune_nome: str | None = None
    zona: str | None = None  # descrizione testuale (fallback)
    zona_tipo: str | None = None  # tassonomia ZonaTipo (Pezzo 6); None = livello comune
    zona_osm_id: str | None = None  # entità OSM selezionata, es. "way/123" (Pezzo 6)
    tema: str | None = None
    cicli: list[str] | None = None
    # "scheda" = fotografia SWOT (Pezzo 4); "idee" = brainstorming a quattro
    # generatori (Pezzo 8); "completa" = UN solo fan-out che alimenta ENTRAMBI
    # gli agenti → report unico (sintesi + SWOT + proposte + idee);
    # "marketing" = brainstorming di marketing territoriale (Pezzo 10): turismo,
    # viabilità, sicurezza, brand — spunti ancorati a una premessa locale + un
    # precedente esterno (fonte web), sezione di report distinta dalle idee.
    modalita: Literal["scheda", "idee", "completa", "marketing"] = "scheda"
    # Popolazione del comune, arricchita SERVER-SIDE dal router (anagrafica
    # locale) — NON arriva dal client. Sopra MACRO_POPULATION l'analisi passa
    # in "modalità macro" (aggregati + top-N, niente enumerazione) per evitare
    # report sterminati sulle città grandi (es. Milano, ~2600 progetti).
    popolazione: int | None = None
    # "Rigenera": salta la cache (F1) e forza un nuovo fan-out. Non entra nella
    # chiave di cache (è un controllo, non un parametro dell'analisi).
    force_refresh: bool = False


# Soglia "città grande": sopra questa popolazione l'analisi è guidata dagli
# aggregati territoriali e dai top progetti per tema, mai dall'enumerazione.
MACRO_POPULATION = 150_000

# Versione dei prompt/contratto: entra nella chiave della cache analisi (F1).
# Bumpare quando un cambio ai prompt o allo schema rende stantie le schede in
# cache, così vengono rigenerate invece di servire output vecchio.
PROMPT_VERSION = "2026-06-22a"


class ProgrammaResponse(BaseModel):
    comune: str
    zona: str | None = None
    # Quadro descrittivo di apertura (prosa, 8-12 frasi): il "racconto" del
    # territorio coi numeri del bundle — risponde al feedback "troppo
    # schematica" del primo collaudo. Vuota se l'LLM non la produce.
    sintesi: str = ""
    # Lettura d'insieme delle IDEE (2-4 frasi): le leve principali del
    # territorio e quali idee sono più promettenti (impatto × fattibilità).
    # Risponde al feedback "sembra un report, non un'analisi" — apre la sezione
    # idee inquadrandole invece di elencarle. Vuota in modalità "scheda".
    idee_sintesi: str = ""
    swot: dict[str, list[VoceSwot]]  # chiavi: forze/debolezze/opportunita/minacce
    proposte: list[Proposta]
    citazioni: list[Resource]  # tutte le fonti risolvibili raccolte dagli specialisti
    disclaimer: str
    generato_il: datetime
    # True quando la scheda è stata servita dalla cache (F1) invece di
    # rigenerata: la UI mostra "analisi da cache · Rigenera". `generato_il`
    # resta la data della generazione originale.
    da_cache: bool = False


class _LlmProgramma(BaseModel):
    """Il sottoinsieme che l'LLM emette — il resto lo assembla l'aggregatore."""

    sintesi: str = ""
    swot: dict[str, list[VoceSwot]] = Field(default_factory=dict)
    proposte: list[Proposta] = Field(default_factory=list)
    disclaimer: str = ""


@dataclass
class ProgrammaOutput:
    """Output-wrapper compatibile con `events.get_outputs()` (legge `.text`)."""

    text: str
    response: ProgrammaResponse | None = None
    evidence_sources: list[str] = field(default_factory=list)


# ─────────────────────────── evidence bundle ────────────────────────────────


def build_programma_task(
    req: ProgrammaRequest,
    zona_info: dict[str, Any] | None = None,
    zone_commerciali: list[dict[str, Any]] | None = None,
    commercio_info: dict[str, Any] | None = None,
    turismo_info: dict[str, Any] | None = None,
    lavoro_info: dict[str, Any] | None = None,
    trasporti_info: dict[str, Any] | None = None,
    welfare_info: dict[str, Any] | None = None,
    istruzione_info: dict[str, Any] | None = None,
    ambiente_info: dict[str, Any] | None = None,
    sanita_info: dict[str, Any] | None = None,
) -> str:
    """Il task inviato ai partecipanti del fan-out (stessa query per tutti).

    `zona_info` è la zona OSM risolta dal Pezzo 6 ({name, centroid, bbox}):
    nome/centroide/bbox vengono iniettati nel task così gli specialisti geo
    (OSM per le distanze, ISPRA per i layer WFS) non rifanno il lookup.

    `zone_commerciali` (lente Commercio/DUC) sono le zone/quartieri candidati
    risolti dal backend: l'agente OSM ci profila la densità commerciale (bbox)
    e l'analisi delle idee localizza il gap commercio ("dove istituire un DUC").
    """
    label = f"{req.cod_comune} ({req.comune_nome})" if req.comune_nome else req.cod_comune
    parts = [
        f"Raccogli evidenze sul comune con codice ISTAT {label}"
    ]
    if zona_info:
        name = zona_info.get("name") or req.zona or "zona selezionata"
        parts.append(f"con particolare attenzione alla zona OSM: {name}")
        centroid = zona_info.get("centroid") or {}
        if centroid:
            parts.append(
                f"(centroide lat={centroid.get('lat'):.5f} lon={centroid.get('lon'):.5f}"
            )
            bbox = zona_info.get("bbox")
            if bbox:
                parts.append(
                    f", bbox sud={bbox[0]:.5f} ovest={bbox[1]:.5f} "
                    f"nord={bbox[2]:.5f} est={bbox[3]:.5f}"
                )
            parts.append(")")
    elif req.zona:
        parts.append(f"con particolare attenzione alla zona: {req.zona}")
    if req.zona_tipo:
        parts.append(f"(tipo di zona: {req.zona_tipo})")
    if req.tema:
        parts.append(f"sul tema: {req.tema}")
    if req.cicli:
        parts.append(f"per i cicli di programmazione: {', '.join(req.cicli)}")
    parts.append(
        "— servono: indicatori socioeconomici, progetti pubblici finanziati, "
        "capacità di spesa storica e dataset rilevanti."
    )
    # Sintesi generale a livello comune che si confronta coi pari: chiedi
    # SEMPRE gli aggregati territoriali (totali per tema, non l'elenco) e il
    # confronto con comuni simili — è la spina dorsale di un'analisi sobria.
    parts.append(
        "Usa come spina dorsale gli AGGREGATI territoriali per tema (totali "
        "finanziato/speso, NON l'elenco esaustivo dei progetti) e, dove i tool "
        "lo permettono, il confronto con COMUNI SIMILI (stessa fascia "
        "dimensionale e regione). Dei singoli progetti cita solo i più "
        "rilevanti per importo."
    )
    if (req.popolazione or 0) >= MACRO_POPULATION:
        tema_hint = (
            f"Concentrati sul tema '{req.tema}'."
            if req.tema
            else "Senza un tema specifico, concentrati sui 3-4 temi a maggiore "
            "dotazione finanziaria."
        )
        parts.append(
            f"MODALITÀ MACRO (città grande, ~{req.popolazione} abitanti): NON "
            "enumerare i progetti (sono troppi) — lavora SOLO con gli aggregati "
            f"per tema e i top progetti per importo di ciascun tema. {tema_hint}"
        )
    if req.modalita in ("idee", "completa"):
        parts.append(
            "MODALITÀ BRAINSTORMING: oltre a quanto sopra, raccogli anche — se i "
            "tuoi tool lo permettono — i temi dove comuni comparabili hanno "
            "finanziato e questo comune no (kind gap_by_tema), i progetti di "
            "comuni simili (kind similar_projects), i progetti locali fermi "
            "(kind stalled_projects), le risorse programmate e non ancora spese "
            "per tema (aggregati territoriali), gli indicatori critici e "
            "l'accessibilità della zona."
        )
        if commercio_info:
            com = commercio_info.get("commercio") or {}
            tot = commercio_info.get("totale") or {}
            src = commercio_info.get("source_url") or ""
            anno = commercio_info.get("anno")
            quota = com.get("quota_unita_locali_pct")
            quota_s = f" ({quota}% del totale)" if quota is not None else ""
            parts.append(
                "LENTE COMMERCIO — DATI ISTAT ASIA GIÀ RACCOLTI (ancora primaria, "
                f"anno {anno}): unità locali di imprese attive nella sezione ATECO G "
                f"(commercio all'ingrosso e al dettaglio) = {com.get('unita_locali')}"
                f"{quota_s}; addetti del commercio = {com.get('addetti')}; "
                f"totale comune = {tot.get('unita_locali')} unità locali, "
                f"{tot.get('addetti')} addetti. "
                f"FONTE DA CITARE VERBATIM: {src} . "
                "USA questi numeri per valutare se il commercio è sottodimensionato "
                "rispetto alla popolazione e ai comuni simili; un'idea-DUC DEVE "
                "citare questa fonte ISTAT come evidenza. SE l'istanza Overpass "
                "risponde, aggiungi la DENSITÀ commerciale (osm_commercial_profile) "
                "come complemento per localizzare il gap."
            )
        else:
            parts.append(
                "LENTE COMMERCIO: l'ancora PRIMARIA è la base imprenditoriale ISTAT "
                "(ASIA imprese attive del comune, ATECO sez. G se disponibile, "
                "altrimenti totale imprese) — raccoglila SEMPRE: non dipende da "
                "Overpass. In più, SE l'istanza Overpass risponde, aggiungi la "
                "DENSITÀ commerciale (OSM osm_commercial_profile sul centro comune) "
                "come complemento. Servono a valutare se il commercio è "
                "sottodimensionato e dove rigenerarlo / istituire un DUC."
            )
        if zone_commerciali:
            righe = []
            for z in zone_commerciali[:2]:
                c = z.get("centroid") or {}
                bb = z.get("bbox")
                bb_s = (
                    f" bbox=[{bb[0]:.5f},{bb[1]:.5f},{bb[2]:.5f},{bb[3]:.5f}]"
                    if bb else ""
                )
                c_s = (
                    f" centroide({c.get('lat'):.5f},{c.get('lon'):.5f})"
                    if c.get("lat") is not None else ""
                )
                righe.append(
                    f"  • {z.get('name') or '(senza nome)'} "
                    f"[{z.get('zona_tipo', 'zona')}]{c_s}{bb_s}"
                )
            parts.append(
                "ZONE CANDIDATE PER IL COMMERCIO (per la localizzazione del gap): "
                "per CIASCUNA profila la densità commerciale con "
                "osm_commercial_profile passando il suo bbox, così la sintesi può "
                "dire IN QUALE zona il commercio è più debole; un'idea-DUC DEVE "
                "nominare una di queste zone.\n" + "\n".join(righe)
            )
        if turismo_info:
            righe_tur = ["LENTE TURISMO/CULTURA — DATI GIÀ RACCOLTI:"]
            tc = turismo_info.get("counts") or {}
            src = turismo_info.get("source_url") or ""
            if tc and src:
                lms = turismo_info.get("landmarks") or []
                nomi = ", ".join(
                    f"{m.get('name')} ({m.get('kind')})" for m in lms if m.get("name")
                ) or "(nessun polo nominato in OSM)"
                righe_tur.append(
                    f"• ASSET (OSM): musei={tc.get('musei')}, monumenti/siti "
                    f"storici={tc.get('monumenti_siti')}, attrazioni={tc.get('attrazioni')}, "
                    f"ricettività(POI)={tc.get('ricettivita')}, cultura(teatri/cinema)="
                    f"{tc.get('cultura')}. Poli nominati: {nomi}. FONTE: {src}"
                )
            ric = turismo_info.get("ricettivita") or {}
            if ric.get("source_url"):
                righe_tur.append(
                    f"• RICETTIVITÀ (ISTAT, anno {ric.get('anno')}): "
                    f"posti letto={ric.get('posti_letto')}, esercizi={ric.get('esercizi')}, "
                    f"camere={ric.get('camere')}. FONTE: {ric.get('source_url')}"
                )
            righe_tur.append(
                "USA questi dati per valutare se il patrimonio è valorizzato/"
                "capitalizzato (asset vs posti letto vs popolazione); un'idea "
                "turismo_cultura DEVE NOMINARE un polo (se elencato) e citare una di "
                "queste fonti (OSM o ISTAT)."
            )
            parts.append("\n".join(righe_tur))
        if lavoro_info:
            st = lavoro_info.get("settori") or {}
            parts.append(
                "LENTE LAVORO/COMPETENZE — DATI ISTAT 8milaCensus (CENSIMENTO 2011, "
                "dato STRUTTURALE): tasso di occupazione="
                f"{lavoro_info.get('tasso_occupazione')}%, disoccupazione="
                f"{lavoro_info.get('tasso_disoccupazione')}%, disoccupazione GIOVANILE="
                f"{lavoro_info.get('tasso_disoccupazione_giovanile')}%, NEET 15-29="
                f"{lavoro_info.get('neet_15_29')}%, attività={lavoro_info.get('tasso_attivita')}%. "
                f"Struttura occupazione per settore: agricolo={st.get('agricolo')}%, "
                f"industriale={st.get('industriale')}%, terziario={st.get('terziario_extracommercio')}%, "
                f"commercio={st.get('commercio')}%. "
                f"FONTE DA CITARE VERBATIM: {lavoro_info.get('source_url')} . "
                "ETICHETTA SEMPRE il dato come 'Censimento 2011' (fotografia strutturale, "
                "non congiunturale). Un'idea 'lavoro' deve ancorarsi a questi numeri "
                "(specie disoccupazione giovanile/NEET) e citare questa fonte."
            )
        if trasporti_info:
            tcc = trasporti_info.get("counts") or {}
            parts.append(
                "LENTE TRASPORTI/MOBILITÀ — DATI OSM GIÀ RACCOLTI: fermate bus="
                f"{tcc.get('fermate_bus')}, autostazioni={tcc.get('autostazioni')}, "
                f"stazioni treno={tcc.get('stazioni_treno')}, tram/metro={tcc.get('tram_metro')}; "
                f"stazione ferroviaria presente: {'sì' if trasporti_info.get('ha_stazione_treno') else 'NO'}. "
                f"FONTE DA CITARE VERBATIM: {trasporti_info.get('source_url')} . USA questi "
                "dati per valutare criticità di accessibilità/TPL (poche fermate per "
                "abitante, assenza di nodo ferroviario, dipendenza dall'auto); un'idea "
                "'trasporti' deve ancorarsi a questi numeri e citare questa fonte."
            )
        if welfare_info:
            parts.append(
                "LENTE WELFARE/COESIONE SOCIALE — DATI ISTAT GIÀ RACCOLTI (popolazione "
                f"residente per età, anno {welfare_info.get('anno')}): indice di vecchiaia="
                f"{welfare_info.get('indice_vecchiaia')} (over-65/under-15 ×100; Italia ~190), "
                f"indice di dipendenza anziani={welfare_info.get('indice_dipendenza_anziani')}, "
                f"indice di dipendenza strutturale={welfare_info.get('indice_dipendenza_strutturale')}, "
                f"over-65={welfare_info.get('pct_over_65')}%, under-15={welfare_info.get('pct_under_15')}%, "
                f"popolazione={welfare_info.get('popolazione')}. "
                f"FONTE DA CITARE VERBATIM: {welfare_info.get('source_url')} . USA questi "
                "numeri per valutare il carico sui servizi socio-assistenziali (un indice "
                "di vecchiaia alto con servizi per anziani scarsi è un bisogno scoperto); "
                "un'idea 'welfare' deve ancorarsi a questi numeri e citare questa fonte."
            )
            inv = welfare_info.get("investimenti_sociali") or {}
            if inv.get("source_url"):
                parts.append(
                    "LATO FINANZIAMENTO — INVESTIMENTI OPENCOESIONE TEMA 'inclusione "
                    f"sociale' del comune: finanziato={inv.get('finanziato_totale')} €, "
                    f"pagato={inv.get('pagamenti_totali')} €, spend ratio="
                    f"{inv.get('spend_ratio')}, progetti={inv.get('progetti_totali')}. "
                    f"FONTE DA CITARE VERBATIM: {inv.get('source_url')} . Usa questi numeri "
                    "per dimensionare un'idea welfare e citarne il finanziamento (es. risorse "
                    "sull'inclusione sociale basse o spese male = leva di intervento)."
                )
        if istruzione_info:
            ord_ = istruzione_info.get("per_ordine") or {}
            alu = istruzione_info.get("alunni_statali")
            alu_txt = (
                f" Alunni nelle scuole statali (primaria + secondaria, a.s. "
                f"{istruzione_info.get('alunni_anno')}): {alu}."
                if alu else ""
            )
            parts.append(
                "LENTE ISTRUZIONE — DATI MIUR Open Data GIÀ RACCOLTI (anagrafe scuole, "
                f"a.s. {istruzione_info.get('anno_scolastico')}): {istruzione_info.get('scuole_totali')} "
                f"plessi ({istruzione_info.get('scuole_statali')} statali, "
                f"{istruzione_info.get('scuole_paritarie')} paritarie) — "
                f"infanzia={ord_.get('infanzia')}, primaria={ord_.get('primaria')}, "
                f"sec. I grado={ord_.get('secondaria_i')}, sec. II grado={ord_.get('secondaria_ii')}.{alu_txt} "
                f"FONTE DA CITARE VERBATIM: {istruzione_info.get('source_url')} . USA questi "
                "numeri per valutare l'offerta scolastica (assenza di un ordine → pendolarismo "
                "scolastico; pochi plessi/alunni per abitante; calo iscritti → rischio "
                "accorpamenti); un'idea 'istruzione' deve ancorarsi a questi numeri e citare questa fonte."
            )
        if ambiente_info:
            parts.append(
                "LENTE AMBIENTE / RISCHIO IDROGEOLOGICO — DATI ISPRA IdroGEO GIÀ "
                "RACCOLTI (livello comunale): pericolosità da FRANA elevata/molto "
                f"elevata (P3+P4) sul {ambiente_info.get('frane_area_pct')}% del "
                f"territorio (popolazione esposta {ambiente_info.get('frane_pop')}, "
                f"{ambiente_info.get('frane_pop_pct')}%); pericolosità IDRAULICA "
                f"(alluvioni) scenario elevato P3 sul {ambiente_info.get('alluvioni_p3_area_pct')}% "
                f"del territorio, scenario medio P2 sul {ambiente_info.get('alluvioni_p2_area_pct')}% "
                f"(popolazione esposta P2 {ambiente_info.get('alluvioni_p2_pop')}, "
                f"{ambiente_info.get('alluvioni_p2_pop_pct')}%). "
                f"FONTE DA CITARE VERBATIM: {ambiente_info.get('source_url')} . USA questi "
                "numeri come VINCOLO di pianificazione: un'idea che insiste su aree a "
                "pericolosità elevata va localizzata altrove o deve includere mitigazione "
                "del rischio. Se le quote sono ~0 dillo (l'assenza di vincolo è essa stessa "
                "evidenza); un'idea 'ambiente' deve ancorarsi a questi numeri e citare questa fonte."
            )
        if sanita_info:
            tip = sanita_info.get("per_tipologia") or {}
            tip_str = ", ".join(f"{k}: {v}" for k, v in tip.items()) or "n.d."
            parts.append(
                "LENTE SANITÀ — DATI Ministero della Salute GIÀ RACCOLTI (anagrafe "
                f"farmacie, presidio sanitario di prossimità): {sanita_info.get('farmacie_totali')} "
                f"farmacie attive nel comune (per tipologia: {tip_str}). "
                f"FONTE DA CITARE VERBATIM: {sanita_info.get('source_url')} . USA questi "
                "numeri per valutare l'accessibilità ai servizi sanitari di base (farmacie "
                "per abitante, aree scoperte); un'idea 'sanita' deve ancorarsi a questi "
                "numeri e citare questa fonte (es. farmacia dei servizi dove mancano "
                "strutture territoriali)."
            )
    if req.modalita in ("marketing", "completa"):
        parts.append(
            "MODALITÀ MARKETING TERRITORIALE: oltre agli indicatori, raccogli gli "
            "ASSET locali valorizzabili (POI, beni culturali, prodotti tipici, reti "
            "— da OSM/CKAN) e gli indicatori di domanda (flussi, demografia). "
            "SOPRATTUTTO: cerca sul WEB iniziative ANALOGHE DI ALTRI ENTI (comuni "
            "simili, Regione, agenzie turistiche, stampa istituzionale) da cui "
            "prendere spunto su turismo, viabilità/mobilità, sicurezza/vivibilità e "
            "attrattività/brand — privilegia fonti istituzionali (site:gov.it)."
        )
    return " ".join(parts)


def _bundle_section(source: str, narrative: str, resources: list[Resource]) -> str:
    lines = [f"=== {source.upper()} ===", narrative.strip() or "(nessun risultato)"]
    if resources:
        lines.append("RISORSE CITABILI (usa questi URL verbatim nelle `evidenze`):")
        for r in resources:
            lines.append(f"- [{r.source or source}] {r.name} | {r.url}")
    return "\n".join(lines)


# Cosa implica ciascun tipo di zona per l'analisi (tassonomia ZonaTipo, Pezzo 6):
# iniettato nella RICHIESTA così SWOT e proposte si tarano sul profilo funzionale
# dell'area selezionata invece di restare generici. Chiave = valore lower-case.
_ZONA_TIPO_FOCUS: dict[str, str] = {
    "industriale": (
        "area produttiva — insediamenti e aree dismesse, infrastrutture "
        "energetiche/logistiche, bonifiche, comunità energetiche, accessibilità merci"
    ),
    "commerciale": (
        "area commerciale/terziaria — attrattività, mobilità e sosta, "
        "rigenerazione del retail, mix funzionale"
    ),
    "portuale": (
        "area portuale/costiera — logistica marittima, interfaccia porto-città, "
        "ambiente costiero, cold ironing, dragaggi"
    ),
    "centro_storico": (
        "centro storico — tutela del patrimonio, turismo, residenzialità, "
        "rigenerazione urbana, accessibilità e ZTL"
    ),
    "verde": (
        "area verde/ambientale — servizi ecosistemici, fruizione, rischio "
        "idrogeologico, forestazione, biodiversità"
    ),
    "agricola": (
        "area agricola/rurale — filiere e irrigazione, dissesto, "
        "multifunzionalità, agro-energia, spopolamento"
    ),
}


def _request_header(req: ProgrammaRequest) -> str:
    label = f"{req.cod_comune} ({req.comune_nome})" if req.comune_nome else req.cod_comune
    rows = [f"comune ISTAT: {label}"]
    if req.zona:
        rows.append(f"zona: {req.zona}" + (f" (tipo: {req.zona_tipo})" if req.zona_tipo else ""))
    if req.zona_tipo:
        focus = _ZONA_TIPO_FOCUS.get(req.zona_tipo.strip().lower())
        if focus:
            rows.append(f"profilo della zona: {focus}")
    if req.tema:
        rows.append(f"tema: {req.tema}")
    if req.cicli:
        rows.append(f"cicli: {', '.join(req.cicli)}")
    if req.popolazione:
        rows.append(f"popolazione: {req.popolazione}")
        if req.popolazione >= MACRO_POPULATION:
            rows.append(
                "scala: città grande → analisi MACRO (aggregati per tema + top "
                "progetti per importo, nessuna enumerazione)"
            )
    return "RICHIESTA:\n" + "\n".join(rows)


def _parse_llm_json(raw: str) -> _LlmProgramma:
    """Estrae il JSON della scheda; tollera fence markdown e preamboli.

    La validazione è PER VOCE: un item malformato (typo nei campi, shape
    sbagliata) viene scartato col log, non invalida l'intera scheda — visto
    in smoke con un modello piccolo che ha emesso `fonte: "ospr"`.
    """
    text = raw.strip()
    if "```" in text:
        # taglia al primo blocco fenced (```json ... ```)
        chunks = text.split("```")
        for chunk in chunks[1:]:
            candidate = chunk.removeprefix("json").strip()
            if candidate.startswith("{"):
                text = candidate
                break
    start = text.find("{")
    if start < 0:
        raise ValueError(f"Nessun oggetto JSON nella risposta del programma_agent: {raw[:200]}")
    end = text.rfind("}")
    # JSON troncato (max_tokens): nessuna chiusura → prendi dal primo `{` in poi
    # e lascia che json_repair chiuda le strutture aperte.
    candidate = text[start : end + 1] if end > start else text[start:]
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        # I modelli, anche a T=0, ogni tanto omettono una virgola o lasciano il
        # JSON troncato: un parse stretto azzererebbe l'intera scheda. Ripara
        # best-effort (json_repair) invece di perdere tutto — la validazione
        # vera resta PER VOCE (sotto) e nei guardrail deterministici.
        from json_repair import repair_json

        log.warning("JSON del programma_agent malformato: riparo best-effort")
        data = repair_json(candidate, return_objects=True)
    if not isinstance(data, dict):
        raise ValueError("La risposta del programma_agent non è un oggetto JSON")

    out = _LlmProgramma(
        sintesi=str(data.get("sintesi") or ""),
        disclaimer=str(data.get("disclaimer") or ""),
    )
    swot_raw = data.get("swot") if isinstance(data.get("swot"), dict) else {}
    for key in SWOT_KEYS:
        items = swot_raw.get(key) if isinstance(swot_raw.get(key), list) else []
        kept: list[VoceSwot] = []
        for item in items:
            try:
                kept.append(VoceSwot.model_validate(item))
            except ValidationError:
                log.warning("voce SWOT '%s' malformata scartata: %.80s", key, item)
        out.swot[key] = kept
    proposte_raw = data.get("proposte") if isinstance(data.get("proposte"), list) else []
    for item in proposte_raw:
        try:
            out.proposte.append(Proposta.model_validate(item))
        except ValidationError:
            log.warning("proposta malformata scartata: %.80s", item)
    return out


# ─────────────────────────── aggregatore ────────────────────────────────────


def _clean_citazioni_for_display(resources: list[Resource]) -> list[Resource]:
    """Normalizza la lista FONTI per la UI (display-only): file/API → sito di
    origine, OSM/Overpass NASCOSTE (dato di mappa, non citazione), dedup per URL
    risolto. Gli URL grezzi restano intatti nella validazione/guardrail (vedi
    `sources.resolve_source_url`): qui tocchiamo solo ciò che vede il cittadino.
    """
    seen: set[str] = set()
    out: list[Resource] = []
    for r in resources:
        resolved = resolve_source_url(r.url)
        if resolved is None:  # OSM/Overpass o URL inutilizzabile → fuori dalle fonti
            continue
        href, name = resolved
        if href in seen:
            continue
        seen.add(href)
        out.append(r.model_copy(update={"url": href, "name": r.name or name}))
    return out


def build_programma_aggregator(
    programma_agent: Agent,
    req: ProgrammaRequest,
    *,
    idee_agent: Agent | None = None,
    marketing_agent: Agent | None = None,
    instructions_hint: str | None = None,
    commercio_info: dict[str, Any] | None = None,
    turismo_info: dict[str, Any] | None = None,
    lavoro_info: dict[str, Any] | None = None,
    trasporti_info: dict[str, Any] | None = None,
    welfare_info: dict[str, Any] | None = None,
    istruzione_info: dict[str, Any] | None = None,
    ambiente_info: dict[str, Any] | None = None,
    sanita_info: dict[str, Any] | None = None,
) -> Callable[..., Awaitable[ProgrammaOutput]]:
    """Aggregatore per ConcurrentBuilder: evidenze → scheda validata.

    Con `modalita="completa"` il bundle di evidenze (la parte costosa: UN solo
    fan-out) alimenta ENTRAMBI gli agenti — `programma_agent` per sintesi+SWOT+
    proposte e `idee_agent` per le idee dei quattro generatori — e le proposte
    vengono fuse nello stesso report, ciascuna validata con le regole della
    propria modalità.

    `instructions_hint` è il gancio parametrico residuo: testo aggiuntivo
    anteposto alla richiesta, senza toccare l'impianto.
    """
    if req.modalita == "completa" and idee_agent is None:
        raise ValueError("modalita='completa' richiede anche idee_agent")
    if req.modalita == "marketing" and marketing_agent is None:
        raise ValueError("modalita='marketing' richiede anche marketing_agent")

    async def aggregate(
        results: list[Any],
        emit: Callable[[dict[str, Any]], None] | None = None,
    ) -> ProgrammaOutput:
        log.info("programma aggregator: %d participant results", len(results))
        sections: list[str] = []
        all_resources: list[Resource] = []

        for result in results:
            exec_id = _executor_id(result)
            tag = _normalise_source_tag(exec_id)
            source = tag or exec_id
            raw_text = _extract_text_from_result(result)
            narrative, resources = ("", [])
            if raw_text:
                narrative, resources = parse_agent_reply(raw_text)
            resources = [r for r in resources if not _is_placeholder_url(r.url)]
            resources = resources + _capture_tool_resources(result, tag)
            if tag:
                resources = [
                    r if r.source else r.model_copy(update={"source": tag})
                    for r in resources
                ]
            # dedupe per URL mantenendo l'ordine — anche DENTRO lo stesso
            # partecipante (più chiamate allo stesso tool → stessa citazione).
            seen = {r.url.strip() for r in all_resources}
            unique: list[Resource] = []
            for r in resources:
                key = r.url.strip()
                if key in seen:
                    continue
                seen.add(key)
                unique.append(r)
            resources = unique
            all_resources.extend(resources)
            sections.append(_bundle_section(str(source), narrative, resources))

        # Ancora COMMERCIO deterministica (ISTAT ASIA): iniettata come sezione di
        # evidenza + risorsa citabile così l'idee_agent può ancorare un'idea-DUC e
        # citare la fonte ISTAT — l'agente ISTAT (LLM) si è dimostrato inaffidabile
        # nel farla emergere. La risorsa entra in `all_resources` (→ citazioni +
        # evidence_urls), quindi una proposta commercio_duc che la cita supera il
        # guardrail e la validazione delle citazioni.
        if commercio_info and commercio_info.get("source_url"):
            com = commercio_info.get("commercio") or {}
            tot = commercio_info.get("totale") or {}
            src = commercio_info["source_url"].strip()
            anno = commercio_info.get("anno")
            quota = com.get("quota_unita_locali_pct")
            quota_s = f" ({quota}% del totale)" if quota is not None else ""
            com_res = Resource(
                name=f"ISTAT ASIA — Unità locali e addetti (commercio, anno {anno})",
                url=src,
                format="CSV",
                source="istat",
            )
            if src not in {r.url.strip() for r in all_resources}:
                all_resources.append(com_res)
            narrative = (
                f"Base imprenditoriale del comune (ISTAT ASIA, anno {anno}). "
                f"Commercio (ATECO sez. G): {com.get('unita_locali')} unità locali "
                f"di imprese attive{quota_s}, {com.get('addetti')} addetti. "
                f"Totale comune: {tot.get('unita_locali')} unità locali, "
                f"{tot.get('addetti')} addetti. Usa questi numeri per valutare se il "
                "commercio è sottodimensionato; un'idea-DUC DEVE citare questa fonte."
            )
            sections.append(_bundle_section("commercio", narrative, [com_res]))

        # Ancora TURISMO/CULTURA deterministica: due fonti citabili complementari —
        # asset culturali OSM (poli nominati, host openstreetmap.org) e capacità
        # ricettiva ISTAT (posti letto/esercizi, host istat.it). Entrambe iniettate
        # come Resource citabile + sezione evidenza, così un'idea turismo_cultura
        # ancora su evidenza reale e supera il guardrail (`_TURISMO_HOSTS`).
        if turismo_info:
            tur_res: list[Resource] = []
            righe: list[str] = []
            tc = turismo_info.get("counts") or {}
            osm_src = (turismo_info.get("source_url") or "").strip()
            if tc and osm_src:
                lms = turismo_info.get("landmarks") or []
                nomi = ", ".join(
                    f"{m.get('name')} ({m.get('kind')})" for m in lms if m.get("name")
                ) or "(nessun polo nominato)"
                tur_res.append(Resource(
                    name="OSM — Asset turistico-culturali del comune (musei, monumenti, attrazioni)",
                    url=osm_src, format="JSON", source="osm",
                ))
                righe.append(
                    f"Asset (OSM) — musei: {tc.get('musei')}, monumenti/siti storici: "
                    f"{tc.get('monumenti_siti')}, attrazioni: {tc.get('attrazioni')}, "
                    f"ricettività(POI): {tc.get('ricettivita')}, cultura: {tc.get('cultura')}. "
                    f"Poli nominati: {nomi}."
                )
            ric = turismo_info.get("ricettivita") or {}
            ric_src = (ric.get("source_url") or "").strip()
            if ric_src:
                tur_res.append(Resource(
                    name=f"ISTAT — Capacità esercizi ricettivi del comune (anno {ric.get('anno')})",
                    url=ric_src, format="CSV", source="istat",
                ))
                righe.append(
                    f"Ricettività (ISTAT, anno {ric.get('anno')}) — posti letto: "
                    f"{ric.get('posti_letto')}, esercizi: {ric.get('esercizi')}, "
                    f"camere: {ric.get('camere')}."
                )
            if tur_res:
                seen = {r.url.strip() for r in all_resources}
                for r in tur_res:
                    if r.url.strip() not in seen:
                        all_resources.append(r)
                        seen.add(r.url.strip())
                narrative = (
                    "Patrimonio turistico-culturale e capacità di accoglienza del comune. "
                    + " ".join(righe)
                    + " Valuta se il patrimonio è valorizzato (asset vs posti letto vs "
                    "popolazione); un'idea turismo_cultura DEVE nominare un polo (se "
                    "disponibile) e citare una di queste fonti."
                )
                sections.append(_bundle_section("turismo", narrative, tur_res))

        # Ancora LAVORO/COMPETENZE deterministica (8milaCensus, censimento 2011):
        # Resource citabile (host ottomilacensus.istat.it ⊃ istat.it → _LAVORO_HOSTS)
        # + sezione evidenza, come commercio/turismo. Dato 2011 etichettato.
        if lavoro_info and lavoro_info.get("source_url"):
            src = lavoro_info["source_url"].strip()
            st = lavoro_info.get("settori") or {}
            lav_res = Resource(
                name="ISTAT 8milaCensus — Indicatori del lavoro del comune (Censimento 2011)",
                url=src,
                format="CSV",
                source="istat",
            )
            if src not in {r.url.strip() for r in all_resources}:
                all_resources.append(lav_res)
            narrative = (
                "Indicatori occupazionali del comune (ISTAT 8milaCensus, Censimento 2011 — "
                "dato strutturale). Tasso di occupazione: "
                f"{lavoro_info.get('tasso_occupazione')}%, disoccupazione: "
                f"{lavoro_info.get('tasso_disoccupazione')}%, disoccupazione giovanile: "
                f"{lavoro_info.get('tasso_disoccupazione_giovanile')}%, NEET 15-29: "
                f"{lavoro_info.get('neet_15_29')}%, attività: {lavoro_info.get('tasso_attivita')}%. "
                f"Occupazione per settore — agricolo: {st.get('agricolo')}%, industriale: "
                f"{st.get('industriale')}%, terziario: {st.get('terziario_extracommercio')}%, "
                f"commercio: {st.get('commercio')}%. Un'idea 'lavoro' ancori su questi numeri "
                "(specie disoccupazione giovanile/NEET) e citi questa fonte; etichetta 'Censimento 2011'."
            )
            sections.append(_bundle_section("lavoro", narrative, [lav_res]))

        # Ancora TRASPORTI/MOBILITÀ deterministica (OSM public-transport): Resource
        # citabile (host openstreetmap.org → _TRASPORTI_HOSTS) + sezione evidenza.
        if trasporti_info and trasporti_info.get("source_url"):
            src = trasporti_info["source_url"].strip()
            tcc = trasporti_info.get("counts") or {}
            tra_res = Resource(
                name="OSM — Nodi del trasporto pubblico del comune (fermate, stazioni)",
                url=src,
                format="JSON",
                source="osm",
            )
            if src not in {r.url.strip() for r in all_resources}:
                all_resources.append(tra_res)
            narrative = (
                "Trasporto pubblico del comune (OSM). Fermate bus: "
                f"{tcc.get('fermate_bus')}, autostazioni: {tcc.get('autostazioni')}, "
                f"stazioni treno: {tcc.get('stazioni_treno')}, tram/metro: {tcc.get('tram_metro')}. "
                f"Stazione ferroviaria presente: {'sì' if trasporti_info.get('ha_stazione_treno') else 'NO'}. "
                "Valuta criticità di accessibilità/TPL (poche fermate vs popolazione, "
                "assenza di nodo ferroviario, dipendenza dall'auto); un'idea 'trasporti' "
                "ancori su questi numeri e citi questa fonte."
            )
            sections.append(_bundle_section("trasporti", narrative, [tra_res]))

        # Ancora WELFARE/COESIONE SOCIALE deterministica (ISTAT DCIS_POPRES1): indici
        # demografici di fragilità come Resource citabile (host esploradati.istat.it ⊃
        # istat.it) + sezione evidenza, come commercio/lavoro. Un'idea welfare ancora
        # su questi numeri e cita la fonte ISTAT.
        if welfare_info and welfare_info.get("source_url"):
            src = welfare_info["source_url"].strip()
            wel_res = Resource(
                name=f"ISTAT 8milaCensus — struttura demografica del comune (Censimento {welfare_info.get('anno')})",
                url=src,
                format="CSV",
                source="istat",
            )
            if src not in {r.url.strip() for r in all_resources}:
                all_resources.append(wel_res)
            narrative = (
                "Struttura demografica e fragilità sociale del comune (ISTAT 8milaCensus, "
                f"Censimento {welfare_info.get('anno')}). Indice di vecchiaia: "
                f"{welfare_info.get('indice_vecchiaia')} (over-65/under-15 ×100; Italia 2011 ~148), "
                f"dipendenza anziani: {welfare_info.get('indice_dipendenza_anziani')}, "
                f"dipendenza giovanile: {welfare_info.get('indice_dipendenza_giovanile')}, "
                f"dipendenza strutturale: {welfare_info.get('indice_dipendenza_strutturale')}, "
                f"grandi anziani 75+: {welfare_info.get('pct_over_75')}%, "
                f"popolazione: {welfare_info.get('popolazione')}. Valuta il carico sui servizi "
                "socio-assistenziali (vecchiaia alta vs servizi per anziani); un'idea 'welfare' "
                "ancori su questi numeri e citi questa fonte."
            )
            wel_resources = [wel_res]
            # Complemento finanziario: investimenti OpenCoesione 'inclusione-sociale'
            # (host opencoesione.gov.it) — citabile per dimensionare/finanziare l'idea.
            inv = welfare_info.get("investimenti_sociali") or {}
            inv_src = (inv.get("source_url") or "").strip()
            if inv_src:
                inv_res = Resource(
                    name="OpenCoesione — Investimenti del comune sul tema inclusione sociale",
                    url=inv_src,
                    format="JSON",
                    source="opencoesione",
                )
                if inv_src not in {r.url.strip() for r in all_resources}:
                    all_resources.append(inv_res)
                wel_resources.append(inv_res)
                narrative += (
                    f" Investimenti OpenCoesione 'inclusione sociale': finanziato "
                    f"{inv.get('finanziato_totale')} €, pagato {inv.get('pagamenti_totali')} €, "
                    f"spend ratio {inv.get('spend_ratio')}, {inv.get('progetti_totali')} progetti."
                )
            sections.append(_bundle_section("welfare", narrative, wel_resources))

        # Ancora ISTRUZIONE deterministica (MIUR Open Data, anagrafe scuole): dotazione
        # scolastica per ordine come Resource citabile (host dati.istruzione.it) +
        # sezione evidenza. Un'idea 'istruzione' ancora sui conteggi e cita la fonte.
        if istruzione_info and istruzione_info.get("source_url"):
            src = istruzione_info["source_url"].strip()
            ord_ = istruzione_info.get("per_ordine") or {}
            ist_res = Resource(
                name=f"MIUR Open Data — anagrafe scuole del comune (a.s. {istruzione_info.get('anno_scolastico')})",
                url=src,
                format="CSV",
                source="miur",
            )
            if src not in {r.url.strip() for r in all_resources}:
                all_resources.append(ist_res)
            alu = istruzione_info.get("alunni_statali")
            alu_txt = (
                f" Alunni nelle statali (primaria + secondaria, a.s. "
                f"{istruzione_info.get('alunni_anno')}): {alu}."
                if alu else ""
            )
            narrative = (
                "Dotazione scolastica del comune (MIUR Open Data, anagrafe scuole, "
                f"a.s. {istruzione_info.get('anno_scolastico')}): {istruzione_info.get('scuole_totali')} "
                f"plessi ({istruzione_info.get('scuole_statali')} statali, "
                f"{istruzione_info.get('scuole_paritarie')} paritarie). Per ordine — infanzia: "
                f"{ord_.get('infanzia')}, primaria: {ord_.get('primaria')}, sec. I grado: "
                f"{ord_.get('secondaria_i')}, sec. II grado: {ord_.get('secondaria_ii')}.{alu_txt} Valuta "
                "l'offerta scolastica (assenza di un ordine = pendolarismo scolastico; pochi plessi "
                "o alunni per abitante); un'idea 'istruzione' ancori su questi numeri e citi questa fonte."
            )
            sections.append(_bundle_section("istruzione", narrative, [ist_res]))

        # Ancora AMBIENTE/RISCHIO IDROGEOLOGICO deterministica (ISPRA IdroGEO):
        # pericolosità frane (P3+P4) e idraulica (alluvioni P3/P2) come Resource
        # citabile (host isprambiente.it) + sezione evidenza. Un'idea 'ambiente'
        # ancora su questi numeri come vincolo di pianificazione e cita la fonte.
        if ambiente_info and ambiente_info.get("source_url"):
            src = ambiente_info["source_url"].strip()
            amb_res = Resource(
                name=f"ISPRA IdroGEO — pericolosità idrogeologica del comune ({ambiente_info.get('nome')})",
                url=src,
                format="JSON",
                source="ispra",
            )
            if src not in {r.url.strip() for r in all_resources}:
                all_resources.append(amb_res)
            narrative = (
                "Rischio idrogeologico del comune (ISPRA IdroGEO, livello comunale). "
                f"Pericolosità da frana elevata/molto elevata (P3+P4): "
                f"{ambiente_info.get('frane_area_pct')}% del territorio, popolazione "
                f"esposta {ambiente_info.get('frane_pop')} ({ambiente_info.get('frane_pop_pct')}%). "
                f"Pericolosità idraulica (alluvioni): scenario elevato P3 su "
                f"{ambiente_info.get('alluvioni_p3_area_pct')}% del territorio, scenario medio "
                f"P2 su {ambiente_info.get('alluvioni_p2_area_pct')}% (popolazione esposta P2 "
                f"{ambiente_info.get('alluvioni_p2_pop')}, {ambiente_info.get('alluvioni_p2_pop_pct')}%). "
                "Vincolo di pianificazione: un'idea su aree a pericolosità elevata va "
                "localizzata altrove o include mitigazione; quote ~0 = assenza di vincolo "
                "(anch'essa evidenza). Un'idea 'ambiente' ancori su questi numeri e citi questa fonte."
            )
            sections.append(_bundle_section("ambiente", narrative, [amb_res]))

        # Ancora SANITÀ deterministica (Ministero della Salute, anagrafe farmacie):
        # dotazione di farmacie come Resource citabile (host dati.salute.gov.it) +
        # sezione evidenza. Un'idea 'sanita' ancora sul conteggio e cita la fonte.
        if sanita_info and sanita_info.get("source_url"):
            src = sanita_info["source_url"].strip()
            tip = sanita_info.get("per_tipologia") or {}
            tip_str = ", ".join(f"{k}: {v}" for k, v in tip.items()) or "n.d."
            san_res = Resource(
                name="Ministero della Salute — anagrafe farmacie del comune",
                url=src,
                format="CSV",
                source="salute",
            )
            if src not in {r.url.strip() for r in all_resources}:
                all_resources.append(san_res)
            narrative = (
                "Dotazione sanitaria di prossimità del comune (Ministero della Salute, "
                f"anagrafe farmacie): {sanita_info.get('farmacie_totali')} farmacie attive "
                f"(per tipologia: {tip_str}). Le farmacie sono il presidio sanitario più "
                "capillare: valuta l'accessibilità ai servizi (farmacie per abitante, aree "
                "scoperte); un'idea 'sanita' ancori su questi numeri e citi questa fonte."
            )
            sections.append(_bundle_section("sanita", narrative, [san_res]))

        evidence_urls = {r.url.strip() for r in all_resources}
        bundle = "\n\n".join(sections)
        prompt_parts = [_request_header(req)]
        if instructions_hint:
            prompt_parts.append(instructions_hint)
        prompt_parts.append("EVIDENZE RACCOLTE:\n\n" + bundle)
        prompt = "\n\n".join(prompt_parts)

        # Etichette "umane" per il feed thinking (U1): cosa sta scrivendo l'LLM.
        _PHASE_LABEL = {
            "programma": "Scrivo l'analisi del territorio",
            "idee": "Genero le idee per il territorio",
            "marketing": "Cerco spunti di marketing territoriale",
        }

        async def _run(agent: Agent, label: str) -> _LlmProgramma:
            fase = _PHASE_LABEL.get(label, label)
            try:
                if emit is not None:
                    # L3: streaming dei token della sintesi → feed "thinking" live.
                    emit({"event": "status", "source": fase, "phase": "start"})
                    stream = agent.run(prompt, stream=True)
                    async for update in stream:
                        if getattr(update, "text", None):
                            emit({"event": "thinking", "source": fase, "delta": update.text})
                    final = await stream.get_final_response()
                    raw = (getattr(final, "text", None) or str(final)).strip()
                    emit({"event": "status", "source": fase, "phase": "end"})
                else:
                    llm_result = await agent.run(prompt)
                    raw = (getattr(llm_result, "text", None) or str(llm_result)).strip()
                return _parse_llm_json(raw)
            except Exception:
                log.exception("%s agent failed; sezione vuota", label)
                if emit is not None:
                    emit({"event": "status", "source": fase, "phase": "error"})
                return _LlmProgramma()

        def _build(parsed: _LlmProgramma, modalita: str) -> ProgrammaResponse:
            resp = ProgrammaResponse(
                comune=req.cod_comune,
                zona=req.zona,
                sintesi=parsed.sintesi,
                swot={k: parsed.swot.get(k, []) for k in SWOT_KEYS},
                proposte=parsed.proposte,
                citazioni=all_resources,
                disclaimer=parsed.disclaimer,
                generato_il=datetime.now(timezone.utc),
            )
            return validate_programma(resp, evidence_urls, modalita=modalita)

        if req.modalita == "completa":
            # ANALISI UNICA (un solo fan-out già pagato): scheda
            # (sintesi+SWOT+proposte) + idee dei generatori + — quando il
            # marketing_agent è disponibile (fonte web attiva) — gli spunti di
            # marketing territoriale. Ogni parte è validata con le regole della
            # propria modalità, poi le proposte sono FUSE in un'unica lista
            # (la categoria resta nel `generatore`/`lente`).
            runs = [_run(programma_agent, "programma"), _run(idee_agent, "idee")]
            if marketing_agent is not None:
                runs.append(_run(marketing_agent, "marketing"))
            parsed = await asyncio.gather(*runs)
            response = _build(parsed[0], "scheda")
            response_idee = _build(parsed[1], "idee")
            response.idee_sintesi = response_idee.sintesi

            def _merge(extra: ProgrammaResponse) -> None:
                titoli = {p.titolo.strip().lower() for p in response.proposte}
                response.proposte += [
                    p for p in extra.proposte
                    if p.titolo.strip().lower() not in titoli
                ]

            _merge(response_idee)
            if marketing_agent is not None:
                _merge(_build(parsed[2], "marketing"))
            if not response.disclaimer.strip() and response_idee.disclaimer.strip():
                response.disclaimer = response_idee.disclaimer
        elif req.modalita == "marketing":
            # Marketing territoriale (Pezzo 10): un solo fan-out alimenta il
            # marketing_agent. La sua sintesi è la lettura d'insieme degli
            # spunti → va in idee_sintesi (intro della sezione marketing), non
            # come quadro territoriale.
            response = _build(await _run(marketing_agent, "marketing"), "marketing")  # type: ignore[arg-type]
            response.idee_sintesi = response.sintesi
            response.sintesi = ""
        else:
            agent = idee_agent if (req.modalita == "idee" and idee_agent) else programma_agent
            response = _build(await _run(agent, req.modalita), req.modalita)
            # In modalità "idee" pura la sintesi prodotta è la lettura delle
            # idee: spostala nel campo dedicato così il frontend la rende in
            # cima alla sezione idee (e non come quadro territoriale).
            if req.modalita == "idee":
                response.idee_sintesi = response.sintesi
                response.sintesi = ""

        # Display-only: fonti chiare (file→origine), OSM nascosto, dedup. La
        # validazione sopra ha già usato gli URL grezzi (evidence_urls intatto).
        response.citazioni = _clean_citazioni_for_display(response.citazioni)
        return ProgrammaOutput(
            text=response.model_dump_json(),
            response=response,
            evidence_sources=sorted({str(r.source) for r in response.citazioni if r.source}),
        )

    return aggregate
