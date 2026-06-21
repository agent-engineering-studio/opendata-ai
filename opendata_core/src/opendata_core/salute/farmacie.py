"""Ministero della Salute Open Data — dotazione sanitaria di prossimità (farmacie).

Conta le FARMACIE attualmente attive di un comune dall'anagrafe nazionale del
Ministero della Salute (NSIS). Le farmacie sono il presidio sanitario più
capillare sul territorio: la loro densità misura l'accessibilità ai servizi
sanitari di prossimità (e la "farmacia dei servizi" — CUP, telemedicina,
screening — è una leva di politica sanitaria per i piccoli comuni).

Perché farmacie e non ospedali/ambulatori: l'anagrafe farmacie è l'UNICA fonte
sanitaria comunale con il **codice ISTAT del comune** (`cod_comune`, 6 cifre) →
join deterministico, zero ambiguità. Ospedali/ricovero hanno solo il NOME comune
(join fragile) e l'anagrafe territoriale STS11 non è pubblicata in forma comunale
pulita → restano follow-up.

Accesso (verificato live):
  - pagina dataset: https://www.dati.salute.gov.it/it/dataset/farmacie/
    espone il link al CSV `/sites/default/files/opendata/FRM_FARMA_5_{YYYYMMDD}.csv`
    (la data = pubblicazione, cambia ad ogni refresh → si risolve scrapando la pagina;
    NON hardcodare la data).
  - host download: www.dati.salute.gov.it (l'host gemello www.salute.gov.it è dietro
    bot-shield e dà 403/404 a fetch programmatico → riscriviamo sempre l'host).
  - separatore ';', encoding latin-1, decimali con virgola; record STORICI presenti
    → si tengono solo le farmacie correnti (`data_fine_validita == "-"`). Alcune righe
    hanno colonne disallineate → guardia: `cod_comune` deve essere 6 cifre.

Licenza dati: Ministero della Salute (NSIS) — IODL 2.0.
"""

from __future__ import annotations

import csv
import io
import logging
import os
import re
import ssl
from datetime import date
from typing import Any

import httpx
from cachetools import TTLCache

log = logging.getLogger("opendata-core.salute.farmacie")

# Il portale dati.salute.gov.it usa un cipher/cert sotto il SECLEVEL 2 di default
# di OpenSSL 3 → handshake rifiutato (curl, più permissivo, passa). Abbassiamo il
# security level a 1 MANTENENDO la verifica del certificato. Workaround comune per
# i portali PA italiani con TLS datato (cfr. nota egress Overpass/SearXNG).
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.set_ciphers("DEFAULT@SECLEVEL=1")

_DATASET_PAGE = os.getenv(
    "SALUTE_FARMACIE_DATASET_URL", "https://www.dati.salute.gov.it/it/dataset/farmacie/"
)
_DOWNLOAD_HOST = os.getenv("SALUTE_DOWNLOAD_HOST", "https://www.dati.salute.gov.it")
_USER_AGENT = os.getenv("SALUTE_USER_AGENT", "opendata-ai/1.0 (+territorial-analysis)")
_HTTP_TIMEOUT = float(os.getenv("SALUTE_HTTP_TIMEOUT", "90"))

# Anagrafe aggiornata di rado → cache lunga; l'URL datato viene ri-risolto a scadenza.
_TTL = int(os.getenv("SALUTE_CACHE_TTL_SECONDS", str(7 * 24 * 3600)))
# {base: {cod_comune: {tipologia: count}}} — l'indice nazionale scaricato una volta.
_index_cache: TTLCache = TTLCache(maxsize=4, ttl=_TTL)
_result_cache: TTLCache = TTLCache(maxsize=2048, ttl=_TTL)

# Path opendata del CSV farmacie nella pagina dataset (id 5).
_CSV_HREF_RE = re.compile(r"/sites/default/files/opendata/FRM_FARMA_5_\d{8}\.csv")
_ISTAT_RE = re.compile(r"^\d{6}$")
# Codici tipologia noti (guardia anti-righe-disallineate).
_TIPOLOGIE_VALIDE = {"1", "2", "3", "4"}


def _norm_istat(cod: str | None) -> str:
    """Codice comune → 6 cifre zero-padded (i nostri codici sono già '072021')."""
    s = (cod or "").strip()
    return s.zfill(6) if s.isdigit() else s


async def _resolve_csv_url(client: httpx.AsyncClient) -> str | None:
    """Risolve l'URL corrente del CSV farmacie dalla pagina dataset (la data cambia)."""
    try:
        resp = await client.get(_DATASET_PAGE)
    except httpx.HTTPError as exc:
        log.warning("pagina dataset farmacie non raggiungibile: %s", exc)
        return None
    if resp.status_code != 200:
        return None
    m = _CSV_HREF_RE.search(resp.text)
    if not m:
        return None
    return f"{_DOWNLOAD_HOST.rstrip('/')}{m.group(0)}"


def _parse_farmacie_csv(text: str) -> dict[str, dict[str, int]]:
    """CSV anagrafe → {cod_comune: {descrizione_tipologia: count}} per le SOLE
    farmacie correnti (data_fine_validita == '-'). Difensivo sulle righe disallineate."""
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    if not reader.fieldnames or "cod_comune" not in reader.fieldnames:
        return {}
    index: dict[str, dict[str, int]] = {}
    for row in reader:
        cod = (row.get("cod_comune") or "").strip()
        if not _ISTAT_RE.match(cod):
            continue  # riga malformata / colonne disallineate
        if (row.get("data_fine_validita") or "").strip() != "-":
            continue  # farmacia cessata / record storico
        if (row.get("codice_tipologia") or "").strip() not in _TIPOLOGIE_VALIDE:
            continue  # guardia: tipologia fuori dal set noto → riga sospetta
        tip = (row.get("descrizione_tipologia") or "Ordinaria").strip() or "Ordinaria"
        index.setdefault(cod, {}).setdefault(tip, 0)
        index[cod][tip] += 1
    return index


async def _load_index() -> dict[str, dict[str, int]] | None:
    """Indice nazionale farmacie correnti per comune. Cache module-level: scaricato
    una volta (~11MB) e riusato per tutti i comuni. None se non disponibile."""
    if _DATASET_PAGE in _index_cache:
        return _index_cache[_DATASET_PAGE]
    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT, headers={"User-Agent": _USER_AGENT},
        follow_redirects=True, verify=_SSL_CTX,
    ) as client:
        url = await _resolve_csv_url(client)
        if not url:
            return None
        try:
            resp = await client.get(url)
        except httpx.HTTPError as exc:
            log.warning("download CSV farmacie fallito (%s): %s", url, exc)
            return None
        if resp.status_code != 200:
            return None
        # encoding latin-1 (accenti nei nomi); il body è bytes → decode esplicito.
        text = resp.content.decode("latin-1", errors="replace")
    index = _parse_farmacie_csv(text)
    if index:
        _index_cache[_DATASET_PAGE] = index
        return index
    return None


async def fetch_farmacie_comune(cod_comune: str) -> dict[str, Any]:
    """Farmacie attive del comune (presidio sanitario di prossimità) dal Min. Salute.

    Join DETERMINISTICO per codice ISTAT (`cod_comune` 6 cifre). Ritorna conteggio
    totale + per tipologia, oppure `trovato=False` se il comune non ha farmacie in
    anagrafe o la fonte non risponde → "dato insufficiente", mai conteggi falsi.
    Cache per comune.
    """
    cod = _norm_istat(cod_comune)
    if not _ISTAT_RE.match(cod):
        return {"trovato": False, "note": f"Codice ISTAT non valido: {cod_comune!r}."}
    if cod in _result_cache:
        return _result_cache[cod]

    index = await _load_index()
    if index is None:
        return {
            "trovato": False,
            "comune": cod,
            "note": "Anagrafe farmacie Ministero della Salute non disponibile.",
        }

    per_tipologia = index.get(cod) or {}
    totale = sum(per_tipologia.values())
    if totale == 0:
        result = {
            "trovato": False,
            "comune": cod,
            "source_url": _DATASET_PAGE,
            "note": f"Nessuna farmacia attiva in anagrafe Ministero della Salute per il comune {cod}.",
        }
        _result_cache[cod] = result
        return result

    result = {
        "trovato": True,
        "comune": cod,
        "farmacie_totali": totale,
        "per_tipologia": dict(sorted(per_tipologia.items(), key=lambda kv: -kv[1])),
        "source_url": _DATASET_PAGE,
        "sources": [
            {
                "url": _DATASET_PAGE,
                "estratto_il": date.today().isoformat(),
                "licenza": "Ministero della Salute (NSIS) — IODL 2.0",
            }
        ],
        "note": (
            f"Anagrafe farmacie Ministero della Salute (NSIS): {totale} farmacie attive nel "
            "comune (presidio sanitario di prossimità). Incrocia con la popolazione per "
            "valutare la densità (farmacie per abitante) e l'accessibilità ai servizi."
        ),
    }
    _result_cache[cod] = result
    return result
