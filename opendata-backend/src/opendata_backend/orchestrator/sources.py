"""Risoluzione di una FONTE chiara per il cittadino (display-only).

Port backend di `opendata-ai-ui/lib/territorioSite.ts::resolveSource` (fix #34):
mai un link a file/API in profondità, sempre una pagina-fonte riconoscibile col
suo nome. In più, qui OSM/Overpass sono trattati come **non citabili**: i dati
OSM alimentano analisi e mappa, ma non compaiono come "fonte/verifica la fonte"
(il dettaglio è già sulla mappa). → `resolve_source_url` ritorna None per OSM.

IMPORTANTE: questa normalizzazione è SOLO per la visualizzazione (lista
`citazioni`). La validazione/guardrail dell'analisi continua a usare gli URL
GREZZI: collassare un URL OpenCoesione `aggregati` o `/progetti/` alla homepage
romperebbe `_generatore_ok` (finestra_finanziamento/gap_comparativo). Per questo
non va applicata a `evidence_urls`.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Fonti note → pagina-portale riconoscibile (mai un file/API in profondità).
_PORTALS: tuple[tuple[str, str, str], ...] = (
    ("isprambiente.it", "https://idrogeo.isprambiente.it/", "ISPRA IdroGEO"),
    ("istat.it", "https://www.istat.it/", "ISTAT"),
    ("dati.gov.it", "https://www.dati.gov.it/", "dati.gov.it"),
    ("ec.europa.eu", "https://ec.europa.eu/eurostat", "Eurostat"),
    ("oecd.org", "https://data.oecd.org/", "OCSE"),
)
# OSM/Overpass: NON citabili (la mappa mostra già il dettaglio). → nascoste.
_HIDDEN_HOSTS: tuple[str, ...] = ("openstreetmap.org", "overpass-api.de", "openstreetmap.de")
_FILE_RE = re.compile(r"\.(csv|json|xml|pbf|zip|xlsx?|geojson|tsv)(\?|#|$)", re.IGNORECASE)


def resolve_source_url(raw: str | None) -> tuple[str, str] | None:
    """Fonte chiara (href, nome) per i cittadini, oppure None se va NASCOSTA.

    None quando: URL vuoto/non http, oppure host OSM/Overpass (dato di mappa, non
    una citazione). Altrimenti: portali noti → loro pagina; OpenCoesione → pagina
    progetto o homepage; file/API/query → origine del sito; resto → URL così com'è.
    """
    if not raw:
        return None
    try:
        u = urlparse(raw.replace("&amp;", "&"))
    except ValueError:
        return None
    if u.scheme not in ("http", "https") or not u.netloc:
        return None
    host = u.hostname.lower().removeprefix("www.") if u.hostname else ""

    if any(host == h or host.endswith("." + h) for h in _HIDDEN_HOSTS):
        return None

    # OpenCoesione: la pagina del SINGOLO progetto è chiara e utile (mai il JSON).
    if host == "opencoesione.gov.it" or host.endswith(".opencoesione.gov.it"):
        # `/it/progetti/CLP/` o l'API `/it/api/progetti/CLP.json` → pagina progetto
        # (la ricerca `/progetti.json` non ha l'id e cade in homepage).
        m = re.search(r"/progetti/([^/.]+)", u.path, re.IGNORECASE)
        if m:
            return (
                f"https://opencoesione.gov.it/it/progetti/{m.group(1).lower()}/",
                "OpenCoesione — progetto",
            )
        return ("https://opencoesione.gov.it/", "OpenCoesione")

    for suffix, url, name in _PORTALS:
        if host == suffix or host.endswith("." + suffix):
            return (url, name)

    # Fonte sconosciuta: file/API/query → niente profondità, l'origine del sito.
    if _FILE_RE.search(u.path) or "/api/" in u.path or u.query:
        return (f"{u.scheme}://{u.netloc}/", host)
    return (raw, host)
