"""Router /quality — Data Quality Lab: diagnosi di un file dati (Punto 01 roadmap).

Espone il motore puro `opendata_core.quality.profile_csv` via HTTP. Deterministico
(niente LLM), autenticato + rate-limited come gli altri endpoint. Accetta il
contenuto inline (`content`) o un `url` scaricato server-side con la stessa
validazione anti-SSRF del proxy dataset.
"""

from __future__ import annotations

import io
import logging
import zipfile

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from opendata_core.quality import (
    advise_enrichment,
    advise_scale,
    build_publish_package,
    csv_to_geojson,
    fix_csv,
    generate_dcat,
    infer_schema,
    json_to_geojson,
    profile_csv,
    profile_geojson,
    summarize_csv,
    validate_dcat,
)

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


class SchemaIn(ProfileIn):
    # Nome tabella desiderato (sanificato come identificatore SQL lato motore).
    table_name: str | None = None


class ConvertIn(ProfileIn):
    # Override colonne coordinate (se l'auto-rilevamento non le trova).
    lat_field: str | None = None
    lon_field: str | None = None


class MetadataIn(ProfileIn):
    # Campi editoriali DCAT-AP_IT che NON si deducono dal file: se forniti
    # riempiono la scheda, altrimenti restano segnaposto in `campi_mancanti`.
    titolo: str | None = None
    descrizione: str | None = None
    licenza: str | None = None
    ente: str | None = None
    tema: str | None = None
    frequenza: str | None = None


class ValidateIn(MetadataIn):
    # Si può validare una scheda DCAT già pronta (`metadata`) oppure generarla al
    # volo dal file (content/url + campi editoriali) e validarla.
    metadata: dict | None = None


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


@router.post("/quality/scale")
async def quality_scale(
    body: ProfileIn,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict:
    """Consigli di scala/performance per un CSV grande: formato colonnare (Parquet),
    indici, partizionamento, esposizione via API. Deterministico. Solo CSV → geo 415.
    """
    text = await _resolve_input(body)
    if _is_geojson(text, (body.format or "").lower()):
        raise HTTPException(
            status_code=415,
            detail="I consigli di scala valgono per i CSV tabellari; per i GeoJSON usa la diagnosi geografica.",
        )
    size_bytes = len(text.encode("utf-8"))
    log.info(
        "/quality/scale subject=%s source=%s bytes=%d",
        user.subject, "url" if body.url else "content", size_bytes,
    )
    return advise_scale(profile_csv(text), size_bytes=size_bytes)


@router.post("/quality/summary")
async def quality_summary(
    body: ProfileIn,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict:
    """Riepiloghi pronti da un CSV: statistiche numeriche, totali per categoria,
    andamenti nel tempo (conteggi per anno). Deterministico. Solo CSV → GeoJSON 415.
    """
    text = await _resolve_input(body)
    if _is_geojson(text, (body.format or "").lower()):
        raise HTTPException(
            status_code=415,
            detail="I riepiloghi tabellari valgono per i CSV; per i GeoJSON usa la diagnosi geografica.",
        )
    log.info(
        "/quality/summary subject=%s source=%s chars=%d",
        user.subject, "url" if body.url else "content", len(text),
    )
    return summarize_csv(text)


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


@router.post("/quality/enrich")
async def quality_enrich(
    body: ProfileIn,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict:
    """Suggerimenti di arricchimento: join codici ISTAT, geocoding indirizzi,
    vocabolari controllati. Solo CSV (deducono dalle colonne tabellari); per i
    GeoJSON le geometrie sono già geo-riferite → 415. Nessuna chiamata di rete:
    euristiche deterministiche sui nomi/tipi delle colonne.
    """
    text = await _resolve_input(body)
    if _is_geojson(text, (body.format or "").lower()):
        raise HTTPException(
            status_code=415,
            detail="I suggerimenti di arricchimento valgono per i CSV tabellari; i GeoJSON sono già geo-riferiti.",
        )
    log.info(
        "/quality/enrich subject=%s source=%s chars=%d",
        user.subject, "url" if body.url else "content", len(text),
    )
    return advise_enrichment(profile_csv(text))


@router.post("/quality/schema")
async def quality_schema(
    body: SchemaIn,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict:
    """Da dato a schema: inferisce schema SQL + DDL (`CREATE TABLE`) da un CSV.

    Profila il CSV, poi `infer_schema` propone tipi SQL, nullabilità, chiave
    primaria (o surrogata) e indici utili (date, codici, colonne categoriali).
    Solo CSV: per i GeoJSON lo schema è la geometria stessa (→ 415).
    """
    text = await _resolve_input(body)
    if _is_geojson(text, (body.format or "").lower()):
        raise HTTPException(
            status_code=415,
            detail="Lo schema relazionale si inferisce dai CSV; per i GeoJSON la struttura è la geometria.",
        )
    log.info(
        "/quality/schema subject=%s source=%s chars=%d",
        user.subject, "url" if body.url else "content", len(text),
    )
    return infer_schema(profile_csv(text), table_name=(body.table_name or "dataset"))


@router.post("/quality/to-geojson")
async def quality_to_geojson(
    body: ConvertIn,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict:
    """Convertitore 1-click: tabella con coordinate → GeoJSON di punti mappabile.

    CSV o array JSON di record: rileva le colonne lat/lon (o usa quelle indicate),
    valida i range WGS84 e produce un FeatureCollection. Un GeoJSON già pronto è
    restituito invariato. Esito in `ok`; con `ok=false` arrivano `candidate_columns`
    perché la UI faccia scegliere le colonne.
    """
    text = await _resolve_input(body)
    stripped = text.lstrip()
    is_json = stripped[:1] in ("[", "{") or (body.format or "").lower() in ("json", "geojson")
    log.info(
        "/quality/to-geojson subject=%s tipo=%s source=%s",
        user.subject, "json" if is_json else "csv", "url" if body.url else "content",
    )
    fn = json_to_geojson if is_json else csv_to_geojson
    return fn(text, lat_field=body.lat_field, lon_field=body.lon_field)


@router.post("/quality/metadata")
async def quality_metadata(
    body: MetadataIn,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict:
    """Genera lo scheletro DCAT-AP_IT (Dataset + Distribution) da un file.

    Profila il file (CSV o GeoJSON), poi `generate_dcat` ricava i campi deducibili
    (formato, media type, schema campi, keyword) e segna `<da compilare>` quelli
    editoriali non passati. Restituisce metadati + `campi_mancanti`.
    """
    text = await _resolve_input(body)
    geo = _is_geojson(text, (body.format or "").lower())
    profile = profile_geojson(text) if geo else profile_csv(text)
    log.info(
        "/quality/metadata subject=%s tipo=%s source=%s",
        user.subject, "geojson" if geo else "csv", "url" if body.url else "content",
    )
    return generate_dcat(
        profile,
        titolo=body.titolo,
        descrizione=body.descrizione,
        licenza=body.licenza,
        ente=body.ente,
        tema=body.tema,
        frequenza=body.frequenza,
        url=body.url,
    )


@router.post("/quality/validate")
async def quality_validate(
    body: ValidateIn,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict:
    """Valida una scheda DCAT-AP_IT: campi obbligatori, licenza aperta, punteggio FAIR.

    Si passa una scheda già pronta (`metadata`, l'output di /quality/metadata) oppure
    un file (content/url + campi editoriali) da cui generarla al volo e validarla.
    Restituisce `{validazione, metadata}`.
    """
    if body.metadata is not None:
        meta = body.metadata
    else:
        text = await _resolve_input(body)
        geo = _is_geojson(text, (body.format or "").lower())
        profile = profile_geojson(text) if geo else profile_csv(text)
        meta = generate_dcat(
            profile, titolo=body.titolo, descrizione=body.descrizione,
            licenza=body.licenza, ente=body.ente, tema=body.tema,
            frequenza=body.frequenza, url=body.url,
        )
    log.info("/quality/validate subject=%s source=%s",
             user.subject, "metadata" if body.metadata is not None else "file")
    return {"validazione": validate_dcat(meta), "metadata": meta}


@router.post("/quality/package")
async def quality_package(
    body: MetadataIn,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> Response:
    """Pacchetto ZIP pronto da pubblicare: dato pulito + scheda DCAT-AP_IT +
    licenza + README con esito FAIR e checklist. CSV o GeoJSON.
    """
    text = await _resolve_input(body)
    geo = _is_geojson(text, (body.format or "").lower())
    if geo:
        data_filename, data_content = "dati.geojson", text
        profile = profile_geojson(text)
    else:
        data_content = fix_csv(text).get("content") or text  # versione corretta nel pacchetto
        data_filename = "dati.csv"
        profile = profile_csv(data_content)

    pkg = build_publish_package(
        profile, data_filename=data_filename, data_content=data_content,
        titolo=body.titolo, descrizione=body.descrizione, licenza=body.licenza,
        ente=body.ente, tema=body.tema, frequenza=body.frequenza, url=body.url,
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in pkg["files"].items():
            zf.writestr(name, content)
    log.info(
        "/quality/package subject=%s tipo=%s valido=%s files=%d",
        user.subject, "geojson" if geo else "csv",
        pkg["validazione"]["valido"], len(pkg["files"]),
    )
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="pacchetto-opendata.zip"'},
    )
