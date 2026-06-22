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

from opendata_core.quality import fix_csv, profile_csv, profile_geojson

from ..auth import ClerkUser
from ..shared.ratelimit import enforce_rate_limit
from .datasets import _validate_proxy_url

log = logging.getLogger("opendata-backend.quality")
router = APIRouter(tags=["quality"])

_MAX_FETCH_BYTES = 16 * 1024 * 1024  # 16 MB
_FETCH_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
# Formati gestiti oggi: tabellari (CSV/TSV/TXT) + geografici (GeoJSON/JSON sniffato).
_ALLOWED_FORMATS = {"", "csv", "tsv", "txt", "geojson", "json"}


class ProfileIn(BaseModel):
    content: str | None = None
    url: str | None = None
    format: str | None = None  # opzionale: csv/tsv/txt o geojson


def _is_geojson(text: str, fmt: str) -> bool:
    """True se il contenuto è GeoJSON (per formato dichiarato o sniff sul testo)."""
    if fmt == "geojson":
        return True
    if fmt in ("csv", "tsv", "txt"):
        return False
    s = text.lstrip()[:4000]
    return s[:1] == "{" and '"type"' in s and any(
        k in s for k in ("FeatureCollection", '"Feature"', '"coordinates"', '"geometries"', '"Topology"')
    )


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


async def _resolve_input(body: ProfileIn) -> str:
    """Valida il formato e risolve il testo da `content` o `url`. Solleva 400/415."""
    fmt = (body.format or "").lower()
    if fmt not in _ALLOWED_FORMATS:
        raise HTTPException(
            status_code=415,
            detail=f"Formato '{fmt}' non ancora supportato dal Quality Lab (oggi: CSV/TSV/TXT, GeoJSON).",
        )
    text = body.content
    if not text and body.url:
        text = await _fetch_text(body.url)
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Fornisci `content` (CSV/GeoJSON) oppure un `url` valido.")
    return text


@router.post("/quality/profile")
async def quality_profile(
    body: ProfileIn,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict:
    """Profila/diagnostica un CSV o un GeoJSON: passa `content` oppure `url`.

    Dispatch automatico sul tipo: GeoJSON → diagnosi geo (CRS, geometrie, validità);
    altrimenti CSV (separatore, profilo colonne). Nessun numero inventato.
    """
    text = await _resolve_input(body)
    geo = _is_geojson(text, (body.format or "").lower())
    log.info(
        "/quality/profile subject=%s tipo=%s source=%s chars=%d",
        user.subject, "geojson" if geo else "csv", "url" if body.url else "content", len(text),
    )
    return profile_geojson(text) if geo else profile_csv(text)


@router.post("/quality/fix")
async def quality_fix(
    body: ProfileIn,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict:
    """Restituisce la versione CORRETTA del CSV + l'elenco delle modifiche.

    Solo correzioni sicure e deterministiche (BOM, intestazioni, spazi, date ISO,
    decimali con virgola → punto, separatore → virgola). Vedi `fix_csv`.

    NB: l'auto-fix dei file geografici (riproiezione in WGS84) avviene nel browser,
    non qui — vedi la pagina Qualità.
    """
    text = await _resolve_input(body)
    if _is_geojson(text, (body.format or "").lower()):
        raise HTTPException(
            status_code=415,
            detail="L'auto-fix dei GeoJSON (riproiezione in WGS84) avviene nel browser, dalla pagina Qualità.",
        )
    log.info(
        "/quality/fix subject=%s source=%s chars=%d",
        user.subject, "url" if body.url else "content", len(text),
    )
    return fix_csv(text)
