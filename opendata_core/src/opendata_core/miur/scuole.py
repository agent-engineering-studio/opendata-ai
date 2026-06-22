"""MIUR Open Data — dotazione scolastica a livello COMUNALE (anagrafe scuole).

Conta i PLESSI per ordine (infanzia / primaria / secondaria I grado / secondaria
II grado) di un comune dai dataset anagrafe MIUR (scuole statali + paritarie).
È l'unica fonte a copertura nazionale che geolocalizza la singola scuola al
comune; misura la dotazione del servizio scolastico sul territorio.

Join (deterministico, dal 2026-06): i CSV MIUR non contengono il codice ISTAT,
ma il codice catastale **Belfiore** (`CODICECOMUNESCUOLA`, es. E038). Si converte
il codice ISTAT della richiesta in Belfiore tramite la tabella statica
`data/istat_catastale.csv` (derivata da ISTAT + Agenzia Entrate, ~7900 comuni) e
si filtra l'anagrafe su quel codice. Niente più match per nome → nessuna
ambiguità sugli omonimi.

Accesso (verificato live):
  https://dati.istruzione.it/opendata/opendata/catalogo/elements1/{SHORT}{AS}{YYYYMMDD}.csv
  - SHORT: SCUANAGRAFESTAT (statali) / SCUANAGRAFEPAR (paritarie)
  - AS: anno scolastico compatto ("202526" = 2025/26); YYYYMMDD: ref ("20250901")
  - separatore ',', UTF-8 senza BOM, quoting CSV standard; valori mancanti = "Non Disponibile"
  - file mancante → il server risponde 200 con una pagina HTML, non un CSV: si
    provano gli anni a ritroso finché l'header non è valido.

Licenza dati: MIUR Open Data — IODL 2.0.
"""

from __future__ import annotations

import csv
import io
import logging
import os
from datetime import date
from importlib.resources import files
from typing import Any

import httpx
from cachetools import TTLCache

log = logging.getLogger("opendata-core.miur.scuole")

_BASE_DEFAULT = os.getenv(
    "MIUR_OPENDATA_BASE_URL",
    "https://dati.istruzione.it/opendata/opendata/catalogo/elements1",
)
_USER_AGENT = os.getenv("MIUR_USER_AGENT", "opendata-ai/1.0 (+territorial-analysis)")
_HTTP_TIMEOUT = float(os.getenv("MIUR_HTTP_TIMEOUT", "90"))
# Quanti anni scolastici provare a ritroso prima di arrendersi.
_YEARS_BACK = int(os.getenv("MIUR_YEARS_BACK", "4"))
# Da quale anno-solare iniziare la ricerca a ritroso. None → year corrente (UTC),
# iniettabile nei test per evitare la dipendenza dall'orologio.
_START_YEAR_ENV = os.getenv("MIUR_START_YEAR")

# Anagrafe annuale → cache lunga (l'anno scolastico cambia una volta l'anno).
_TTL = int(os.getenv("MIUR_CACHE_TTL_SECONDS", str(7 * 24 * 3600)))
# dataset → {cod_catastale: [ordine, ...]}
_index_cache: TTLCache = TTLCache(maxsize=8, ttl=_TTL)
# (start_year, base, cod_istat) → risultato
_result_cache: TTLCache = TTLCache(maxsize=2048, ttl=_TTL)
# Mappa ISTAT→Belfiore (lazy, statica): {cod_istat: cod_catastale}.
_catastale_map: dict[str, str] | None = None

# SHORT name del file per dataset.
_DATASETS = {
    "statali": "SCUANAGRAFESTAT",
    "paritarie": "SCUANAGRAFEPAR",
}
_HEADER_SENTINEL = "ANNOSCOLASTICO"


def _catastale_for_istat(cod_istat: str) -> str | None:
    """Codice catastale Belfiore (es. 'E038') per un codice ISTAT comune ('072021').

    Carica una volta la tabella statica `data/istat_catastale.csv` (shippata nel
    package). None se il codice ISTAT non è mappato (comune nuovo/variato → la
    tabella va aggiornata)."""
    global _catastale_map
    if _catastale_map is None:
        m: dict[str, str] = {}
        raw = files("opendata_core.miur.data").joinpath("istat_catastale.csv").read_text(
            encoding="utf-8"
        )
        reader = csv.DictReader(io.StringIO(raw))
        for row in reader:
            istat = (row.get("cod_istat") or "").strip()
            cat = (row.get("cod_catastale") or "").strip().upper()
            if istat and cat:
                m[istat] = cat
        _catastale_map = m
    return _catastale_map.get((cod_istat or "").strip())


def _macro_ordine(desc: str) -> str | None:
    """`DESCRIZIONETIPOLOGIAGRADOISTRUZIONESCUOLA` → macro-ordine, o None per gli
    aggregatori amministrativi (istituti comprensivi, CPIA) che non sono plessi.

    Il campo mescola grado e indirizzo: la secondaria II grado non ha un'etichetta
    unica (liceo, istituto tecnico, IST PROF, magistrale, convitto…) → è il
    "resto" dopo aver isolato infanzia/primaria/primo grado e gli aggregatori.
    """
    d = (desc or "").upper()
    if "ISTITUTO COMPRENSIVO" in d or "CENTRO TERRITORIALE" in d or "ISTITUTO PRINCIPALE" in d:
        return None
    if "INFANZIA" in d:
        return "infanzia"
    if "PRIMARIA" in d:
        return "primaria"
    if "PRIMO GRADO" in d:
        return "secondaria_i"
    return "secondaria_ii"


def _school_years(start_year: int) -> list[tuple[str, str, str]]:
    """(label '2025/26', AS '202526', ref '20250901') a ritroso da start_year."""
    out: list[tuple[str, str, str]] = []
    for y in range(start_year, start_year - _YEARS_BACK - 1, -1):
        out.append((f"{y}/{(y + 1) % 100:02d}", f"{y}{(y + 1) % 100:02d}", f"{y}0901"))
    return out


def _build_url(base: str, short: str, as_compact: str, ref: str) -> str:
    return f"{base.rstrip('/')}/{short}{as_compact}{ref}.csv"


def _parse_anagrafe(text: str) -> dict[str, list[tuple[str, str]]]:
    """CSV anagrafe → {cod_catastale: [(ordine, codice_scuola), ...]}.

    Una riga = un plesso (`CODICESCUOLA`). Chiave = codice catastale Belfiore
    (`CODICECOMUNESCUOLA`) → join deterministico col codice ISTAT via tabella.
    Conserva anche `CODICESCUOLA` per agganciare gli alunni (ALUCORSOINDCLASTA,
    che non ha colonna comune). Gli aggregatori amministrativi (`_macro_ordine`
    None) sono esclusi. Parsing per NOME colonna (header reale), robusto fra
    statali (20 col) e paritarie (14).
    """
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or _HEADER_SENTINEL not in reader.fieldnames:
        return {}
    index: dict[str, list[tuple[str, str]]] = {}
    for row in reader:
        ordine = _macro_ordine(row.get("DESCRIZIONETIPOLOGIAGRADOISTRUZIONESCUOLA", ""))
        if ordine is None:
            continue
        cat = (row.get("CODICECOMUNESCUOLA") or "").strip().upper()
        if not cat:
            continue
        codice = (row.get("CODICESCUOLA") or "").strip().upper()
        index.setdefault(cat, []).append((ordine, codice))
    return index


async def _load_index(
    dataset: str, base: str, start_year: int
) -> tuple[dict[str, list[tuple[str, str]]], str, str] | None:
    """Indice nazionale del dataset (cod. catastale → plessi), con anno effettivo e
    URL. Cache module-level per (dataset, base): l'anagrafe nazionale si scarica
    una volta e serve tutti i comuni. None se nessun anno è disponibile."""
    ck = (dataset, base)
    if ck in _index_cache:
        return _index_cache[ck]
    short = _DATASETS[dataset]
    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT, headers={"User-Agent": _USER_AGENT}, follow_redirects=True
    ) as client:
        for label, as_compact, ref in _school_years(start_year):
            url = _build_url(base, short, as_compact, ref)
            try:
                resp = await client.get(url)
            except httpx.HTTPError as exc:
                log.warning("MIUR %s %s non raggiungibile: %s", dataset, label, exc)
                continue
            if resp.status_code != 200:
                continue
            text = resp.text
            # File mancante = pagina HTML con 200: scartala e prova l'anno prima.
            if not text.lstrip().startswith(_HEADER_SENTINEL):
                continue
            index = _parse_anagrafe(text)
            if index:
                out = (index, label, url)
                _index_cache[ck] = out
                return out
    return None


# Dataset alunni per plesso. Convenzione data diversa dall'anagrafe: ref =
# {anno_fine}0831. Quattro dataset (statali/paritarie × primaria-secondaria/infanzia);
# header diversi: ALU* → ALUNNIMASCHI/FEMMINE; INFANZIA* → BAMBINIMASCHI/FEMMINE.
#   chiave logica → (SHORT, colonna_maschi, colonna_femmine, settore: statali|paritarie)
_STUDENT_DATASETS: dict[str, tuple[str, str, str, str]] = {
    "ps_statali": ("ALUCORSOINDCLASTA", "ALUNNIMASCHI", "ALUNNIFEMMINE", "statali"),
    "ps_paritarie": ("ALUCORSOINDCLAPAR", "ALUNNIMASCHI", "ALUNNIFEMMINE", "paritarie"),
    "inf_statali": ("INFANZIACLASTA", "BAMBINIMASCHI", "BAMBINIFEMMINE", "statali"),
    "inf_paritarie": ("INFANZIACLAPAR", "BAMBINIMASCHI", "BAMBINIFEMMINE", "paritarie"),
}


def _to_int(raw: str | None) -> int:
    try:
        return int((raw or "").strip())
    except (TypeError, ValueError):
        return 0


def _alunni_years(start_year: int) -> list[tuple[str, str, str]]:
    """(label '2024/25', AS '202425', ref '20250831') a ritroso da start_year.

    NB: il ref usa l'anno DI FINE dell'anno scolastico (+1), a differenza
    dell'anagrafe che usa l'anno di inizio (…0901)."""
    out: list[tuple[str, str, str]] = []
    for y in range(start_year, start_year - _YEARS_BACK - 1, -1):
        out.append((f"{y}/{(y + 1) % 100:02d}", f"{y}{(y + 1) % 100:02d}", f"{y + 1}0831"))
    return out


def _parse_counts(text: str, m_col: str, f_col: str) -> dict[str, int]:
    """CSV alunni/bambini → {codice_scuola: totale} (maschi + femmine, sommati su
    tutte le righe del plesso). m_col/f_col variano fra ALU* e INFANZIA*."""
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or _HEADER_SENTINEL not in reader.fieldnames:
        return {}
    out: dict[str, int] = {}
    for row in reader:
        cod = (row.get("CODICESCUOLA") or "").strip().upper()
        if not cod:
            continue
        out[cod] = out.get(cod, 0) + _to_int(row.get(m_col)) + _to_int(row.get(f_col))
    return out


async def _load_count_index(
    key: str, base: str, start_year: int
) -> tuple[dict[str, int], str, str] | None:
    """Indice nazionale {cod. scuola → conteggio} per uno dei `_STUDENT_DATASETS`,
    con anno e URL. Cache module-level. Best-effort (anni a ritroso): gli alunni sono
    pubblicati con ritardo rispetto all'anagrafe. None se nessun anno disponibile."""
    ck = ("students", key, base)
    if ck in _index_cache:
        return _index_cache[ck]
    short, m_col, f_col, _settore = _STUDENT_DATASETS[key]
    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT, headers={"User-Agent": _USER_AGENT}, follow_redirects=True
    ) as client:
        for label, as_compact, ref in _alunni_years(start_year):
            url = f"{base.rstrip('/')}/{short}{as_compact}{ref}.csv"
            try:
                resp = await client.get(url)
            except httpx.HTTPError as exc:
                log.warning("MIUR %s %s non raggiungibile: %s", short, label, exc)
                continue
            if resp.status_code != 200 or not resp.text.lstrip().startswith(_HEADER_SENTINEL):
                continue
            idx = _parse_counts(resp.text, m_col, f_col)
            if idx:
                out = (idx, label, url)
                _index_cache[ck] = out
                return out
    return None


async def fetch_scuole_comune(
    cod_comune: str,
    base_url: str | None = None,
    start_year: int | None = None,
) -> dict[str, Any]:
    """Dotazione scolastica del comune (plessi per ordine) da MIUR Open Data.

    Somma scuole statali + paritarie. Join DETERMINISTICO: codice ISTAT →
    codice catastale Belfiore (tabella statica) → filtro su `CODICECOMUNESCUOLA`.
    Ritorna `trovato=False` quando il comune non compare nell'anagrafe, il codice
    ISTAT non è mappato, o il dataset non è disponibile → "dato insufficiente",
    mai conteggi falsi. Cache per (anno, comune).
    """
    cod = (cod_comune or "").strip()
    catastale = _catastale_for_istat(cod)
    if not catastale:
        return {
            "trovato": False,
            "comune": cod,
            "note": (
                f"Codice ISTAT {cod!r} non mappato a un codice catastale "
                "(tabella istat_catastale da aggiornare?): join MIUR non possibile."
            ),
        }
    base = (base_url or _BASE_DEFAULT).rstrip("/")
    sy = start_year if start_year is not None else (
        int(_START_YEAR_ENV) if _START_YEAR_ENV else date.today().year
    )
    ck = (sy, base, cod)
    if ck in _result_cache:
        return _result_cache[ck]

    statali = await _load_index("statali", base, sy)
    if statali is None:
        return {
            "trovato": False,
            "comune": cod,
            "note": "Anagrafe scuole statali MIUR non disponibile (nessun anno scolastico recente).",
        }
    # Paritarie best-effort: se manca, la dotazione resta valida sulle sole statali.
    paritarie = await _load_index("paritarie", base, sy)

    conteggi = {"infanzia": 0, "primaria": 0, "secondaria_i": 0, "secondaria_ii": 0}
    statali_tot = paritarie_tot = 0
    # CODICESCUOLA del comune per settore → join coi dataset alunni.
    codici: dict[str, list[str]] = {"statali": [], "paritarie": []}

    def _accumulate(loaded: tuple[dict, str, str] | None, is_statale: bool) -> None:
        nonlocal statali_tot, paritarie_tot
        if not loaded:
            return
        index, _label, _url = loaded
        for ordine, codice in index.get(catastale, ()):
            conteggi[ordine] += 1
            if is_statale:
                statali_tot += 1
            else:
                paritarie_tot += 1
            if codice:
                codici["statali" if is_statale else "paritarie"].append(codice)

    _accumulate(statali, is_statale=True)
    _accumulate(paritarie, is_statale=False)

    totale = statali_tot + paritarie_tot
    anno = statali[1]
    source_url = statali[2]
    if totale == 0:
        result = {
            "trovato": False,
            "comune": cod,
            "anno_scolastico": anno,
            "source_url": source_url,
            "note": (
                f"Nessuna scuola in anagrafe MIUR {anno} per il comune {cod} "
                f"(codice catastale {catastale})."
            ),
        }
        _result_cache[ck] = result
        return result

    # Alunni (best-effort): per i CODICESCUOLA del comune, somma i 4 dataset MIUR
    # (statali/paritarie × primaria-secondaria/infanzia). Bucket disgiunti → totale
    # senza doppi conteggi; "di cui infanzia"/"di cui paritarie" sono tagli trasversali.
    # Pubblicati con ritardo → anno spesso diverso dall'anagrafe (riportato a parte).
    buckets: dict[str, int] = {}
    alunni_anno: str | None = None
    if statali_tot or paritarie_tot:
        for key, (_short, _m, _f, settore) in _STUDENT_DATASETS.items():
            comune_codici = codici[settore]
            if not comune_codici:
                continue
            loaded = await _load_count_index(key, base, sy)
            if not loaded:
                continue
            idx_al, lbl, _u = loaded
            alunni_anno = alunni_anno or lbl
            buckets[key] = sum(idx_al.get(c, 0) for c in comune_codici)

    s_ps = buckets.get("ps_statali", 0)
    p_ps = buckets.get("ps_paritarie", 0)
    s_inf = buckets.get("inf_statali", 0)
    p_inf = buckets.get("inf_paritarie", 0)
    alunni_totali = s_ps + p_ps + s_inf + p_inf
    has_alunni = alunni_totali > 0
    alunni_infanzia = s_inf + p_inf
    alunni_paritarie = p_ps + p_inf
    alunni_statali = s_ps + s_inf  # statali, tutti gli ordini (compresa infanzia)

    note = (
        f"Anagrafe scuole MIUR (statali + paritarie), a.s. {anno}. {totale} plessi: "
        f"{conteggi['infanzia']} infanzia, {conteggi['primaria']} primaria, "
        f"{conteggi['secondaria_i']} sec. I grado, {conteggi['secondaria_ii']} sec. II grado. "
        "Conteggio della dotazione scolastica sul territorio (esclusi gli aggregatori "
        "amministrativi: istituti comprensivi, CPIA)."
    )
    if has_alunni:
        note += (
            f" Alunni totali (a.s. {alunni_anno}): {alunni_totali} — di cui {alunni_infanzia} "
            f"nell'infanzia e {alunni_paritarie} nelle paritarie. Incrocia con la popolazione "
            "per il peso della popolazione scolastica."
        )

    result = {
        "trovato": True,
        "comune": cod,
        "anno_scolastico": anno,
        "scuole_totali": totale,
        "scuole_statali": statali_tot,
        "scuole_paritarie": paritarie_tot,
        "per_ordine": conteggi,
        "alunni_totali": alunni_totali if has_alunni else None,
        "alunni_infanzia": alunni_infanzia if has_alunni else None,
        "alunni_paritarie": alunni_paritarie if has_alunni else None,
        "alunni_statali": alunni_statali if has_alunni else None,
        "alunni_anno": alunni_anno,
        "source_url": source_url,
        "sources": [
            {
                "url": source_url,
                "estratto_il": date.today().isoformat(),
                "licenza": "MIUR Open Data — IODL 2.0",
            }
        ],
        "note": note,
    }
    _result_cache[ck] = result
    return result
