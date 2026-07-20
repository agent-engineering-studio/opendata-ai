"""Discovery deterministica dell'Idea Lab: dataset CKAN + progetti finanziati.

Nessun LLM qui. Due sorgenti, entrambe fail-safe (lista vuota su errore):

- **Dataset**: `package_search` sul portale CKAN configurato (default
  dati.gov.it filtrato sull'organizzazione della Regione), ogni pacchetto
  valutato con `opendata_core.maturity.quality.assess_quality` → stelle,
  licenza, freschezza. È l'evidenza "su quali dati puoi costruire".
- **Finanziabilità**: progetti comparabili già finanziati in regione via
  OpenCoesione (`search_projects` per tema) — l'evidenza che idee simili
  hanno già trovato fondi pubblici.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from opendata_core.ckan import CkanClient
from opendata_core.maturity.models import DatasetInput
from opendata_core.maturity.quality import assess_quality
from opendata_core.opencoesione import OpenCoesioneClient

from ..config import Settings, resolve_ideas_oc_cod_regione, resolve_ideas_portal_fq
from .models import AREAS, FundingProject, IdeaDataset

log = logging.getLogger("opendata-backend.ideas")

# Stopword minime per estrarre keyword di ricerca dal testo della sfida.
_STOPWORDS = frozenset(
    "il lo la i gli le un uno una di a da in con su per tra fra e o ma che chi "
    "cui non più meno come dove quando anche ancora quindi però essere avere "
    "fare sono siamo sia del della dei delle dello degli nel nella nei nelle "
    "sul sulla sui sulle questo questa questi queste quello quella vorrei "
    "vogliamo voglio serve servono bisogno problema sfida idea dati dataset "
    "comune città regione puglia ente nostro nostra".split()
)

_WORD_RE = re.compile(r"[a-zàèéìòù]{4,}", re.IGNORECASE)


def extract_keywords(text: str, *, limit: int = 6) -> list[str]:
    """Parole significative del testo sfida, in ordine di apparizione, senza duplicati."""
    seen: list[str] = []
    for word in _WORD_RE.findall(text.lower()):
        if word not in _STOPWORDS and word not in seen:
            seen.append(word)
        if len(seen) >= limit:
            break
    return seen


def build_search_query(*, area: str | None, challenge_text: str) -> str:
    keywords = extract_keywords(challenge_text)
    if not keywords and area:
        keywords = AREAS[area]["keywords"].split()[:4]
    return " ".join(keywords) or (AREAS[area]["label"].lower() if area else "open data")


def _candidate_queries(*, area: str | None, challenge_text: str) -> list[str]:
    """Query in ordine di specificità decrescente: la prima non vuota vince.

    Sui portali CKAN reali (dati.gov.it) il q multi-termine è edismax con
    minimum-should-match: più keyword = più restrittivo, e la query piena
    spesso torna 0. Si rilassa quindi in tre passi: AND pieno → OR sulle
    prime keyword → keyword generiche dell'area.
    """
    keywords = extract_keywords(challenge_text)
    queries: list[str] = []
    if keywords:
        queries.append(" ".join(keywords))
        if len(keywords) > 1:
            queries.append(" OR ".join(keywords[:3]))
    if area:
        queries.append(" OR ".join(AREAS[area]["keywords"].split()[:4]))
    return queries or ["open data"]


def _dataset_page_url(pkg: dict, base_url: str) -> str:
    name = pkg.get("name") or pkg.get("id") or ""
    return f"{base_url.rstrip('/')}/dataset/{name}"


def _quality_note(ds: DatasetInput, stars: int, freshness: int | None) -> str:
    parts = [f"{stars}/5 stelle"]
    parts.append("licenza aperta" if ds.license_is_open else "licenza da verificare")
    if freshness is not None:
        parts.append(f"aggiornato {freshness} giorni fa")
    return ", ".join(parts)


async def discover_datasets(
    settings: Settings,
    *,
    area: str | None,
    challenge_text: str,
    base_url: str | None = None,
    client: CkanClient | None = None,
) -> list[IdeaDataset]:
    """package_search + assess_quality; lista vuota su qualunque errore di rete.

    Le query candidate si provano in ordine di specificità: appena una torna
    risultati ci si ferma (rilassamento progressivo, vedi _candidate_queries).
    """
    portal = base_url or settings.ideas_portal_base_url or settings.ckan_default_base_url

    async def _search(c: CkanClient) -> dict | None:
        for query in _candidate_queries(area=area, challenge_text=challenge_text):
            params: dict[str, object] = {"q": query, "rows": settings.ideas_max_datasets}
            portal_fq = resolve_ideas_portal_fq(settings)
            if portal_fq:
                params["fq"] = portal_fq
            result = await c.action("package_search", base_url=portal, params=params)
            if (result or {}).get("results"):
                return result
        return result

    try:
        if client is not None:
            result = await _search(client)
        else:
            async with CkanClient() as c:
                result = await _search(c)
    except Exception:
        log.warning("ideas discovery failed (portal=%s)", portal, exc_info=True)
        return []

    now = datetime.now(UTC)
    found: list[IdeaDataset] = []
    for pkg in (result or {}).get("results", []):
        try:
            ds = DatasetInput.from_ckan(pkg)
            score = assess_quality(ds, as_of=now)
        except Exception:
            log.warning("assess_quality failed for pkg=%s", pkg.get("id"), exc_info=True)
            continue
        found.append(
            IdeaDataset(
                id=ds.id,
                title=ds.title or pkg.get("name") or ds.id,
                url=_dataset_page_url(pkg, portal),
                notes=(ds.description or "")[:280],
                organization=(pkg.get("organization") or {}).get("title") or "",
                formats=sorted(set(ds.formats)),
                modified=ds.modified.date().isoformat() if ds.modified else None,
                stars=score.stars_5,
                license_open=score.license_open,
                freshness_days=score.freshness_days,
                quality_note=_quality_note(ds, score.stars_5, score.freshness_days),
            )
        )
    return found


async def discover_funding(
    settings: Settings,
    *,
    area: str | None,
    client: OpenCoesioneClient | None = None,
) -> list[FundingProject]:
    """Progetti comparabili finanziati in regione (OpenCoesione), fail-safe."""
    tema = AREAS[area]["oc_tema"] if area else None
    cod_regione = resolve_ideas_oc_cod_regione(settings)
    try:
        if client is not None:
            result = await client.search_projects(
                cod_regione=cod_regione,
                tema=tema,
                limit=settings.ideas_max_funding,
            )
        else:
            async with OpenCoesioneClient() as c:
                result = await c.search_projects(
                    cod_regione=cod_regione,
                    tema=tema,
                    limit=settings.ideas_max_funding,
                )
    except Exception:
        log.warning("ideas funding discovery failed (tema=%s)", tema, exc_info=True)
        return []

    projects: list[FundingProject] = []
    for rec in (result or {}).get("results", []):
        try:
            projects.append(
                FundingProject(
                    clp=str(rec.get("clp") or ""),
                    titolo=(rec.get("titolo") or "(senza titolo)")[:160],
                    tema=rec.get("tema"),
                    stato=rec.get("stato"),
                    ciclo=rec.get("ciclo"),
                    finanziamento_totale=rec.get("finanziamento_totale"),
                    url=rec.get("url"),
                )
            )
        except Exception:
            continue
    return projects
