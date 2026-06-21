"""MIUR Open Data — dotazione scolastica a livello COMUNALE (anagrafe scuole).

Conta i PLESSI per ordine (infanzia / primaria / secondaria I grado / secondaria
II grado) di un comune dai dataset anagrafe MIUR (scuole statali + paritarie).
È l'unica fonte a copertura nazionale che geolocalizza la singola scuola al
comune; misura la dotazione del servizio scolastico sul territorio.

Vincolo del join (lezione della discovery 2026-06): i CSV MIUR **non contengono
il codice ISTAT** del comune, solo `DESCRIZIONECOMUNE` (nome), `REGIONE` e il
codice catastale Belfiore (`CODICECOMUNESCUOLA`, es. E038). Il join è quindi per
NOME comune normalizzato (+ `regione` opzionale per disambiguare gli omonimi).
Upgrade futuro: tabella ISTAT↔Belfiore per un match deterministico.

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
import unicodedata
from datetime import date
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
# dataset → {nome_comune_norm: [(ordine, regione_norm), ...]}
_index_cache: TTLCache = TTLCache(maxsize=8, ttl=_TTL)
# (statali_year, comune_norm, regione_norm) → risultato
_result_cache: TTLCache = TTLCache(maxsize=2048, ttl=_TTL)

# SHORT name del file per dataset.
_DATASETS = {
    "statali": "SCUANAGRAFESTAT",
    "paritarie": "SCUANAGRAFEPAR",
}
_HEADER_SENTINEL = "ANNOSCOLASTICO"


def _norm(value: str | None) -> str:
    """Normalizza un nome (comune/regione) per il match: NFKD, niente accenti né
    punteggiatura, spazi collassati, maiuscolo. 'Forlì'→'FORLI', "FORLI'"→'FORLI'."""
    if not value:
        return ""
    s = unicodedata.normalize("NFKD", str(value))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = "".join(c if c.isalnum() else " " for c in s)
    return " ".join(s.split()).upper()


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
    """CSV anagrafe → {nome_comune_norm: [(ordine, regione_norm), ...]}.

    Una riga = un plesso (`CODICESCUOLA`). Gli aggregatori amministrativi
    (`_macro_ordine` None) sono esclusi. Parsing per NOME colonna (header reale),
    robusto all'ordine e alle colonne extra fra statali (20) e paritarie (14).
    """
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or _HEADER_SENTINEL not in reader.fieldnames:
        return {}
    index: dict[str, list[tuple[str, str]]] = {}
    for row in reader:
        ordine = _macro_ordine(row.get("DESCRIZIONETIPOLOGIAGRADOISTRUZIONESCUOLA", ""))
        if ordine is None:
            continue
        comune = _norm(row.get("DESCRIZIONECOMUNE"))
        if not comune:
            continue
        index.setdefault(comune, []).append((ordine, _norm(row.get("REGIONE"))))
    return index


async def _load_index(
    dataset: str, base: str, start_year: int
) -> tuple[dict[str, list[tuple[str, str]]], str, str] | None:
    """Indice nazionale del dataset (nome comune → plessi), con anno effettivo e
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


async def fetch_scuole_comune(
    comune_nome: str,
    regione: str | None = None,
    base_url: str | None = None,
    start_year: int | None = None,
) -> dict[str, Any]:
    """Dotazione scolastica del comune (plessi per ordine) da MIUR Open Data.

    Somma scuole statali + paritarie. Join per NOME comune normalizzato; passa
    `regione` per disambiguare gli omonimi. Ritorna `trovato=False` quando il
    comune non compare nell'anagrafe (nome assente, o dataset non disponibile)
    → "dato insufficiente", mai conteggi falsi. Cache per (anno, comune, regione).
    """
    nome_norm = _norm(comune_nome)
    reg_norm = _norm(regione) if regione else None
    if not nome_norm:
        return {"trovato": False, "note": "comune_nome mancante: join MIUR non possibile."}
    base = (base_url or _BASE_DEFAULT).rstrip("/")
    sy = start_year if start_year is not None else (
        int(_START_YEAR_ENV) if _START_YEAR_ENV else date.today().year
    )
    ck = (sy, base, nome_norm, reg_norm or "")
    if ck in _result_cache:
        return _result_cache[ck]

    statali = await _load_index("statali", base, sy)
    if statali is None:
        return {
            "trovato": False,
            "comune": comune_nome,
            "note": "Anagrafe scuole statali MIUR non disponibile (nessun anno scolastico recente).",
        }
    # Paritarie best-effort: se manca, la dotazione resta valida sulle sole statali.
    paritarie = await _load_index("paritarie", base, sy)

    conteggi = {"infanzia": 0, "primaria": 0, "secondaria_i": 0, "secondaria_ii": 0}
    statali_tot = paritarie_tot = 0

    def _accumulate(loaded: tuple[dict, str, str] | None, is_statale: bool) -> None:
        nonlocal statali_tot, paritarie_tot
        if not loaded:
            return
        index, _label, _url = loaded
        for ordine, reg in index.get(nome_norm, ()):
            if reg_norm and reg != reg_norm:
                continue
            conteggi[ordine] += 1
            if is_statale:
                statali_tot += 1
            else:
                paritarie_tot += 1

    _accumulate(statali, is_statale=True)
    _accumulate(paritarie, is_statale=False)

    totale = statali_tot + paritarie_tot
    anno = statali[1]
    source_url = statali[2]
    if totale == 0:
        result = {
            "trovato": False,
            "comune": comune_nome,
            "anno_scolastico": anno,
            "source_url": source_url,
            "note": (
                f"Nessuna scuola trovata per '{comune_nome}' nell'anagrafe MIUR {anno} "
                "(verifica il nome del comune o l'eventuale regione di disambiguazione)."
            ),
        }
        _result_cache[ck] = result
        return result

    result = {
        "trovato": True,
        "comune": comune_nome,
        "anno_scolastico": anno,
        "scuole_totali": totale,
        "scuole_statali": statali_tot,
        "scuole_paritarie": paritarie_tot,
        "per_ordine": conteggi,
        "source_url": source_url,
        "sources": [
            {
                "url": source_url,
                "estratto_il": date.today().isoformat(),
                "licenza": "MIUR Open Data — IODL 2.0",
            }
        ],
        "note": (
            f"Anagrafe scuole MIUR (statali + paritarie), a.s. {anno}. {totale} plessi: "
            f"{conteggi['infanzia']} infanzia, {conteggi['primaria']} primaria, "
            f"{conteggi['secondaria_i']} sec. I grado, {conteggi['secondaria_ii']} sec. II grado. "
            "Conteggio della dotazione scolastica sul territorio (esclusi gli aggregatori "
            "amministrativi: istituti comprensivi, CPIA)."
        ),
    }
    _result_cache[ck] = result
    return result
