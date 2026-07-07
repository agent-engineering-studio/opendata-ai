"""BDAP — Banca Dati delle Amministrazioni Pubbliche: bilanci/spesa dei comuni (#100).

`bdap-opendata.rgs.mef.gov.it` è un portale Drupal custom, ma espone una Action API
CKAN-compatibile sotto un path non standard (`/SpodCkanApi/api/3/action/*`, verificato
live) e, per dataset, una risorsa **OData queryabile riga per riga**
(`/ODataProxy/MdData('{resource_id}@rgs')/DataRows`, `$filter` reale — nessun download
bulk necessario). La serie "SIOPE Movimenti cumulati mensili di Entrata/Spesa"
(un dataset per regione/anno/tipo) copre ogni comune SIOPE-aderente con il dettaglio
per titolo di bilancio, aggiornata mensilmente fino all'anno corrente — verificato per
Puglia dal 2014 al 2026. La serie più vecchia "Gestione finanziaria Enti Locali" (con
classificazione titolo/categoria/risorsa) è invece ferma al 2013-2015: scartata.

I nomi dei campi OData sono generati con un suffisso hash (es. `Cccodice_istat_c174690678`),
ma sono **stabili a livello di piattaforma** per lo stesso campo logico, non casuali
per-risorsa: verificato identico su 3 risorse indipendenti (2023 Lazio Spesa, 2024
Puglia Spesa, 2024 Puglia Entrata) — sia nome che posizione.

`package_show` accetta solo l'UUID del dataset (mai lo slug/name) — la risoluzione
regione/anno/tipo → UUID passa quindi da un indice costruito paginando
`package_search` (query letterale "SIOPE Movimenti cumulati", ~520 dataset) e filtrando
per titolo esatto: le query Solr composte con più termini/frasi si sono rivelate
inaffidabili (0 risultati anche su termini presenti nel titolo).
"""

from __future__ import annotations

import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any

import httpx
from cachetools import TTLCache

log = logging.getLogger("opendata-core.bdap")

_BASE_DEFAULT = os.getenv("BDAP_BASE_URL", "https://bdap-opendata.rgs.mef.gov.it")
_SEARCH_PATH = "/SpodCkanApi/api/3/action/package_search"
_SHOW_PATH = "/SpodCkanApi/api/3/action/package_show"
_USER_AGENT = os.getenv("BDAP_USER_AGENT", "opendata-ai/1.0 (+territorial-analysis)")
_HTTP_TIMEOUT = float(os.getenv("BDAP_HTTP_TIMEOUT", "60"))
_YEARS_BACK = 3
_SEARCH_QUERY = "SIOPE Movimenti cumulati"
_PAGE_SIZE = 100
_ODATA_TOP = 1000

_TTL = int(os.getenv("BDAP_CACHE_TTL_SECONDS", str(24 * 3600)))
_index_cache: TTLCache = TTLCache(maxsize=1, ttl=_TTL)  # {"index": {(anno,regione,tipo): package_id}}
_odata_cache: TTLCache = TTLCache(maxsize=256, ttl=_TTL)  # package_id -> odata_url
_result_cache: TTLCache = TTLCache(maxsize=512, ttl=_TTL)

_TITLE_RE = re.compile(r"^(\d{4}) - (.+?) - SIOPE Movimenti cumulati mensili di (Entrata|Spesa)$")

# Provincia ISTAT (3 cifre) → regione ISTAT (2 cifre). Fonte: ISTAT 8milaCensus
# Province_Regioni_Italia_confini_2011.csv (stessa fonte di opendata_core.census).
# Le 4 province sarde soppresse nel 2016 (104-107) restano per compatibilità storica.
_PROVINCIA_REGIONE: dict[str, str] = {
    "001": "01", "002": "01", "003": "01", "004": "01", "005": "01", "006": "01",
    "007": "02",
    "008": "07", "009": "07", "010": "07", "011": "07",
    "012": "03", "013": "03", "014": "03", "015": "03", "016": "03", "017": "03",
    "018": "03", "019": "03", "020": "03",
    "021": "04", "022": "04",
    "023": "05", "024": "05", "025": "05", "026": "05", "027": "05", "028": "05", "029": "05",
    "030": "06", "031": "06", "032": "06",
    "033": "08", "034": "08", "035": "08", "036": "08", "037": "08", "038": "08",
    "039": "08", "040": "08",
    "041": "11", "042": "11", "043": "11", "044": "11",
    "045": "09", "046": "09", "047": "09", "048": "09", "049": "09", "050": "09",
    "051": "09", "052": "09", "053": "09",
    "054": "10", "055": "10",
    "056": "12", "057": "12", "058": "12", "059": "12", "060": "12",
    "061": "15", "062": "15", "063": "15", "064": "15", "065": "15",
    "066": "13", "067": "13", "068": "13", "069": "13",
    "070": "14",
    "071": "16", "072": "16", "073": "16", "074": "16", "075": "16",
    "076": "17", "077": "17",
    "078": "18", "079": "18", "080": "18",
    "081": "19", "082": "19", "083": "19", "084": "19", "085": "19", "086": "19",
    "087": "19", "088": "19", "089": "19",
    "090": "20", "091": "20", "092": "20",
    "093": "06",
    "094": "14",
    "095": "20",
    "096": "01",
    "097": "03", "098": "03",
    "099": "08",
    "100": "09",
    "101": "18", "102": "18",
    "103": "01",
    "104": "20", "105": "20", "106": "20", "107": "20",
    "108": "03",
    "109": "11",
    "110": "16",
}

# Come titolate nei dataset BDAP (verificato via package_search) — usate solo per
# ricavare la chiave dell'indice dal codice regione di un comune; il parsing del
# titolo reale (_TITLE_RE) è la fonte di verità per il nome esatto.
_REGIONE_NOME: dict[str, str] = {
    "01": "Piemonte", "02": "Valle d'Aosta", "03": "Lombardia", "04": "Trentino-Alto Adige",
    "05": "Veneto", "06": "Friuli-Venezia Giulia", "07": "Liguria", "08": "Emilia-Romagna",
    "09": "Toscana", "10": "Umbria", "11": "Marche", "12": "Lazio", "13": "Abruzzo",
    "14": "Molise", "15": "Campania", "16": "Puglia", "17": "Basilicata", "18": "Calabria",
    "19": "Sicilia", "20": "Sardegna",
}

# Campi OData verificati live (nome hash stabile per lo stesso campo logico, non
# per-risorsa) su: 2023 Lazio Spesa, 2024 Puglia Spesa, 2024 Puglia Entrata.
_F_PROVINCIA = "Cccodice_istat_p579596766"
_F_COMUNE = "Cccodice_istat_c174690678"
_F_DENOMINAZIONE = "Ccdescrizione_e1917009725"
_F_ANNO_MESE = "Ccanno_mese_cale259090347"
_F_CODICE_TITOLO = "Cccodice_titolo1460397607"
_F_DESCRIZIONE_TITOLO = "Ccdescrizione_t1210507133"
_F_POPOLAZIONE = "Ccpopolazione_i2144107841"
_F_IMPORTO = "Ccimporto_cumula615775458"

_ATOM_NS = "{http://www.w3.org/2005/Atom}"
_M_NS = "{http://schemas.microsoft.com/ado/2007/08/dataservices/metadata}"


class BdapError(RuntimeError):
    """Raised when the BDAP API returns an error or a transport error occurs."""


def _parse_title(title: str) -> tuple[int, str, str] | None:
    m = _TITLE_RE.match((title or "").strip())
    if not m:
        return None
    return int(m.group(1)), m.group(2), m.group(3)


def _parse_odata_entries(xml_text: str) -> list[dict[str, str]]:
    """Estrae le righe di un feed Atom/OData come dict {campo_hash: valore}."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    rows: list[dict[str, str]] = []
    for entry in root.findall(f"{_ATOM_NS}entry"):
        props = entry.find(f".//{_M_NS}properties")
        if props is None:
            continue
        rows.append({child.tag.split("}", 1)[-1]: (child.text or "") for child in props})
    return rows


async def _fetch_json(client: httpx.AsyncClient, url: str, params: dict[str, Any]) -> Any:
    try:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        raise BdapError(f"Transport error on {url}: {exc}") from exc
    except ValueError as exc:
        raise BdapError(f"Non-JSON response from {url}: {exc}") from exc


async def _build_dataset_index(
    client: httpx.AsyncClient, base: str
) -> dict[tuple[int, str, str], str]:
    """Indice {(anno, regione, tipo): package_id}, costruito paginando package_search.

    `package_show` non accetta lo slug (solo l'UUID), quindi l'unico modo di risolvere
    una (regione, anno, tipo) è cercarla nel catalogo — cache lunga perché il catalogo
    cambia raramente (nuovo anno ~1 volta l'anno, aggiornamenti mensili in-place).
    """
    if "index" in _index_cache:
        return _index_cache["index"]
    index: dict[tuple[int, str, str], str] = {}
    start = 0
    while True:
        body = await _fetch_json(
            client, base + _SEARCH_PATH, {"q": _SEARCH_QUERY, "rows": _PAGE_SIZE, "start": start}
        )
        results = (body.get("result") or {}).get("results") or []
        if not results:
            break
        for r in results:
            parsed = _parse_title(r.get("title", ""))
            if parsed:
                index[parsed] = r.get("id")
        if len(results) < _PAGE_SIZE:
            break
        start += _PAGE_SIZE
    _index_cache["index"] = index
    return index


async def _resolve_odata_url(client: httpx.AsyncClient, base: str, package_id: str) -> str | None:
    if package_id in _odata_cache:
        return _odata_cache[package_id]
    body = await _fetch_json(client, base + _SHOW_PATH, {"id": package_id})
    if not body.get("success"):
        return None
    for r in (body.get("result") or {}).get("resources") or []:
        if r.get("resource_type") == "OData" and r.get("url"):
            _odata_cache[package_id] = r["url"]
            return r["url"]
    return None


async def _query_odata(
    client: httpx.AsyncClient, odata_url: str, filter_expr: str
) -> list[dict[str, str]]:
    resp = await client.get(odata_url, params={"$filter": filter_expr, "$top": _ODATA_TOP})
    resp.raise_for_status()
    return _parse_odata_entries(resp.text)


def _aggregate_per_titolo(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], str | None, float | None]:
    """Una voce per titolo di bilancio, tenendo il mese più recente (cumulato = running total)."""
    denominazione: str | None = None
    popolazione: float | None = None
    latest_mese: dict[str, str] = {}
    by_titolo: dict[str, dict[str, Any]] = {}
    for row in rows:
        denominazione = denominazione or row.get(_F_DENOMINAZIONE) or None
        if popolazione is None:
            pop_raw = row.get(_F_POPOLAZIONE)
            if pop_raw:
                try:
                    popolazione = float(pop_raw)
                except ValueError:
                    pass
        titolo = row.get(_F_CODICE_TITOLO, "")
        mese = row.get(_F_ANNO_MESE, "")
        if titolo not in latest_mese or mese > latest_mese[titolo]:
            latest_mese[titolo] = mese
            try:
                importo = round(float(row.get(_F_IMPORTO) or 0.0), 2)
            except ValueError:
                importo = 0.0
            by_titolo[titolo] = {
                "codice_titolo": titolo,
                "descrizione": row.get(_F_DESCRIZIONE_TITOLO, ""),
                "importo_cumulato": importo,
                "mese_riferimento": mese,
            }
    voci = sorted(by_titolo.values(), key=lambda v: v["importo_cumulato"], reverse=True)
    return voci, denominazione, popolazione


async def fetch_bilancio_comune(
    cod_comune: str, *, anno: int | None = None, base_url: str | None = None
) -> dict[str, Any]:
    """Bilancio SIOPE del comune (entrate/spese cumulate per titolo, anno più recente).

    Fonte: BDAP (RGS) — serie "SIOPE Movimenti cumulati mensili di Entrata/Spesa",
    un dataset per regione/anno, interrogato via OData filtrato su
    (codice_istat_provincia, codice_istat_comune) — nessun download bulk. Prova
    `anno` (o l'anno corrente) e retrocede fino a `_YEARS_BACK` anni se il comune non
    ha righe (non SIOPE-aderente per quell'anno, o dataset non ancora pubblicato).
    """
    cod = (cod_comune or "").strip()
    if len(cod) != 6 or not cod.isdigit():
        return {
            "comune": cod, "trovato": False,
            "note": "Codice ISTAT comune non valido (attese 6 cifre: provincia+comune).",
        }
    provincia, comune_prog = cod[:3], cod[3:]
    regione_code = _PROVINCIA_REGIONE.get(provincia)
    if regione_code is None:
        return {"comune": cod, "trovato": False, "note": f"Provincia {provincia} non mappata."}
    regione_nome = _REGIONE_NOME[regione_code]

    base = (base_url or _BASE_DEFAULT).rstrip("/")
    start_year = anno or date.today().year
    ck = (base, cod, start_year)
    if ck in _result_cache:
        return _result_cache[ck]

    filt = f"{_F_PROVINCIA} eq '{provincia}' and {_F_COMUNE} eq '{comune_prog}'"
    used_year: int | None = None
    entrate_rows: list[dict[str, str]] = []
    spese_rows: list[dict[str, str]] = []

    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT, headers={"User-Agent": _USER_AGENT}, follow_redirects=True
    ) as client:
        index = await _build_dataset_index(client, base)
        for y in range(start_year, start_year - _YEARS_BACK - 1, -1):
            year_entrate: list[dict[str, str]] = []
            year_spese: list[dict[str, str]] = []
            pkg_entrata = index.get((y, regione_nome, "Entrata"))
            pkg_spesa = index.get((y, regione_nome, "Spesa"))
            if pkg_entrata:
                odata_url = await _resolve_odata_url(client, base, pkg_entrata)
                if odata_url:
                    year_entrate = await _query_odata(client, odata_url, filt)
            if pkg_spesa:
                odata_url = await _resolve_odata_url(client, base, pkg_spesa)
                if odata_url:
                    year_spese = await _query_odata(client, odata_url, filt)
            if year_entrate or year_spese:
                used_year, entrate_rows, spese_rows = y, year_entrate, year_spese
                break

    if used_year is None:
        result = {
            "comune": cod, "trovato": False,
            "note": "Nessun dato BDAP/SIOPE trovato per gli anni recenti.",
        }
        _result_cache[ck] = result
        return result

    entrate, denom_e, pop_e = _aggregate_per_titolo(entrate_rows)
    spese, denom_s, pop_s = _aggregate_per_titolo(spese_rows)
    source_url = f"{base}/tema/151_bilanci-degli-enti-della-pubblica-amministrazione"

    result = {
        "comune": cod,
        "denominazione": denom_e or denom_s,
        "anno": used_year,
        "popolazione": pop_e if pop_e is not None else pop_s,
        "entrate": entrate,
        "totale_entrate": round(sum(v["importo_cumulato"] for v in entrate), 2),
        "spese": spese,
        "totale_spese": round(sum(v["importo_cumulato"] for v in spese), 2),
        "source_url": source_url,
        "sources": [
            {
                "url": source_url,
                "estratto_il": date.today().isoformat(),
                "licenza": "BDAP (Ragioneria Generale dello Stato) — Creative Commons Attribution",
            }
        ],
        "trovato": True,
        "note": (
            f"BDAP/SIOPE, movimenti cumulati mensili di entrata/spesa per titolo di "
            f"bilancio, anno {used_year} (aggiornato mensilmente; importi = cumulato "
            "al mese più recente disponibile, non l'intero esercizio se l'anno è in corso)."
        ),
    }
    _result_cache[ck] = result
    return result
