"""Router /quality — Data Quality Lab: diagnosi di un file dati (Punto 01 roadmap).

Espone il motore puro `opendata_core.quality.profile_csv` via HTTP. Deterministico
(niente LLM), autenticato + rate-limited come gli altri endpoint. Accetta il
contenuto inline (`content`) o un `url` scaricato server-side con la stessa
validazione anti-SSRF del proxy dataset.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from opendata_core.quality import profile_csv

from ..auth import ClerkUser
from ..shared.ratelimit import enforce_rate_limit
from .datasets import _validate_proxy_url

log = logging.getLogger("opendata-backend.quality")
router = APIRouter(tags=["quality"])

_MAX_FETCH_BYTES = 16 * 1024 * 1024  # 16 MB
_FETCH_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
# Formati testuali tabellari gestiti oggi dal motore CSV (TSV/TXT delimitati inclusi).
_CSV_FORMATS = {"", "csv", "tsv", "txt"}


class ProfileIn(BaseModel):
    content: str | None = None
    url: str | None = None
    format: str | None = None  # opzionale; oggi: CSV/TSV/TXT


async def _fetch_text(url: str) -> str:
    _validate_proxy_url(url)  # rifiuta reti private/loopback (anti-SSRF)
    async with httpx.AsyncClient(
        timeout=_FETCH_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": "opendata-ai/1.0 (+quality)"},
    ) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Errore scaricando l'URL: {exc}") from exc
    raw = resp.content[:_MAX_FETCH_BYTES]
    enc = resp.encoding or "utf-8"
    try:
        return raw.decode(enc, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


@router.post("/quality/profile")
async def quality_profile(
    body: ProfileIn,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict:
    """Profila/diagnostica un CSV: passa `content` (testo) oppure `url`.

    Ritorna il report di `profile_csv` (separatore, profilo colonne, findings,
    punteggio). Nessun numero inventato: solo ciò che si misura sul file.
    """
    fmt = (body.format or "csv").lower()
    if fmt not in _CSV_FORMATS:
        raise HTTPException(
            status_code=415,
            detail=f"Formato '{fmt}' non ancora supportato dal Quality Lab (oggi: CSV/TSV/TXT).",
        )
    text = body.content
    if not text and body.url:
        text = await _fetch_text(body.url)
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Fornisci `content` (CSV) oppure un `url` valido.")

    log.info(
        "/quality/profile subject=%s source=%s chars=%d",
        user.subject, "url" if body.url else "content", len(text),
    )
    return profile_csv(text)
