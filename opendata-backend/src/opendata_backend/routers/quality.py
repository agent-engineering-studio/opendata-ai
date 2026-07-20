"""Router /quality — Data Quality Lab: diagnosi di un file dati (Punto 01 roadmap).

Espone il motore puro `opendata_core.quality.profile_csv` via HTTP. Deterministico
(niente LLM), autenticato + rate-limited come gli altri endpoint. Accetta il
contenuto inline (`content`) o un `url` scaricato server-side con la stessa
validazione anti-SSRF del proxy dataset.
"""

from __future__ import annotations

import base64
import binascii
import io
import logging
import zipfile

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from opendata_core.quality import (
    advise_enrichment,
    advise_hvd,
    advise_scale,
    build_normalization,
    build_publish_package,
    csv_to_geojson,
    csv_to_parquet,
    fix_csv,
    generate_dcat,
    generate_schema_org,
    infer_geo_schema,
    infer_schema,
    json_to_geojson,
    profile_csv,
    profile_geojson,
    shapefile_to_geojson,
    summarize_csv,
    validate_dcat,
    validate_schema_org,
    xlsx_to_csv,
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


class HvdIn(ProfileIn):
    # Titolo editoriale del dataset: opzionale, migliora la stima HVD.
    titolo: str | None = None


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
    # Si può validare una scheda già pronta (`metadata`, DCAT o schema.org — il
    # vocabolario si riconosce dal campo `profilo`) oppure generarla al volo dal
    # file (content/url + campi editoriali) e validarla.
    metadata: dict | None = None
    # Vocabolario da generare al volo quando `metadata` non è passato: "dcat"
    # (default, compatibilità) o "schema_org".
    vocabolario: str | None = None


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


async def _fetch_bytes(url: str) -> bytes:
    """Variante binaria di `_fetch_text`: stessa anti-SSRF + cap 16 MB, niente decode."""
    _validate_proxy_url(url)
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
    return resp.content[:_MAX_FETCH_BYTES]


class BinaryIn(BaseModel):
    """Input binario per i convertitori server-side (#157): base64 nel body o URL.

    `content_base64` è coerente con l'output base64 di /quality/to-parquet ed è
    l'opzione più semplice per REST/A2A (nessun multipart). In alternativa `url`,
    scaricato server-side con la stessa anti-SSRF del proxy dataset.
    """

    content_base64: str | None = None
    url: str | None = None


async def _resolve_bytes(body: BinaryIn) -> bytes:
    """Risolve i byte da `content_base64` o `url`. Solleva 400 (input) / 413 (troppo grande)."""
    if body.content_base64:
        try:
            data = base64.b64decode(body.content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"content_base64 non valido: {exc}") from exc
    elif body.url:
        data = await _fetch_bytes(body.url)
    else:
        raise HTTPException(status_code=400, detail="Fornisci `content_base64` oppure un `url` valido.")
    if not data:
        raise HTTPException(status_code=400, detail="Il file è vuoto.")
    if len(data) > _MAX_FETCH_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File troppo grande (> {_MAX_FETCH_BYTES // (1024 * 1024)} MB).",
        )
    return data


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


@router.post("/quality/normalize")
async def quality_normalize(
    body: SchemaIn,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict:
    """Normalizzazione & modello: tabelle di lookup + viste SQL da un CSV.

    Completa `/quality/schema`: `build_normalization` estrae le colonne
    categoriali ripetute in tabelle di lookup (DDL + INSERT con i valori reali)
    e propone viste di aggregazione (totali per categoria, andamento per anno,
    pivot categoria×anno quando entrambe esistono). Solo CSV (→ 415 per GeoJSON).
    """
    text = await _resolve_input(body)
    if _is_geojson(text, (body.format or "").lower()):
        raise HTTPException(
            status_code=415,
            detail="La normalizzazione (lookup/viste) vale per i CSV tabellari; i GeoJSON hanno un altro schema.",
        )
    log.info(
        "/quality/normalize subject=%s source=%s chars=%d",
        user.subject, "url" if body.url else "content", len(text),
    )
    return build_normalization(text, table_name=(body.table_name or "dataset"))


@router.post("/quality/geo-schema")
async def quality_geo_schema(
    body: SchemaIn,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict:
    """Da GeoJSON a schema geografico: DDL PostGIS + comando GeoPackage.

    Completa `/quality/schema` sul lato geografico: `infer_geo_schema` deduce
    tipo di geometria e schema delle proprietà, genera il `CREATE TABLE`
    PostGIS (colonna `geom` + indice GIST) e il comando `ogr2ogr` equivalente
    per il GeoPackage. Solo GeoJSON (→ 415 per CSV).
    """
    text = await _resolve_input(body)
    if not _is_geojson(text, (body.format or "").lower()):
        raise HTTPException(
            status_code=415,
            detail="Lo schema geografico vale per i GeoJSON; per i CSV usa /quality/schema.",
        )
    log.info(
        "/quality/geo-schema subject=%s source=%s chars=%d",
        user.subject, "url" if body.url else "content", len(text),
    )
    return infer_geo_schema(text, table_name=(body.table_name or "dataset"))


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


@router.post("/quality/hvd")
async def quality_hvd(
    body: HvdIn,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict:
    """Stima High-Value Dataset (#102): il file rientra in una delle 6 categorie UE?

    Euristica deterministica su nomi colonna/titolo/nome file (Reg. 2023/138):
    ogni categoria stimata porta confidenza esplicita e indizi — mai un verdetto
    secco. CSV e GeoJSON (un GeoJSON è geospaziale per natura).
    """
    text = await _resolve_input(body)
    geo = _is_geojson(text, (body.format or "").lower())
    profile = profile_geojson(text) if geo else profile_csv(text)
    result = advise_hvd(profile, titolo=body.titolo, url=body.url)
    log.info(
        "/quality/hvd subject=%s tipo=%s source=%s categorie=%d",
        user.subject, "geojson" if geo else "csv",
        "url" if body.url else "content", len(result["categorie"]),
    )
    return result


@router.post("/quality/to-parquet")
async def quality_to_parquet(
    body: ProfileIn,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> Response:
    """Convertitore avanzato (#101): CSV → Parquet colonnare e compresso.

    Concretizza il consiglio "formato colonnare" di /quality/scale: tipi inferiti
    con le regole del profilo (una colonna è tipizzata solo se tutti i valori
    aderiscono, altrimenti resta testo — nessuna perdita). Risposta binaria come
    /quality/package. Richiede l'extra `converters` (pyarrow): se assente → 501.
    """
    text = await _resolve_input(body)
    if _is_geojson(text, (body.format or "").lower()):
        raise HTTPException(
            status_code=415,
            detail="L'export Parquet vale per i CSV tabellari; per i GeoJSON usa GeoPackage (/quality/geo-schema).",
        )
    result = csv_to_parquet(text)
    if not result["ok"]:
        # pyarrow non installato → 501 (capability assente), input illeggibile → 422
        status = 501 if "pyarrow" in (result["error"] or "") else 422
        raise HTTPException(status_code=status, detail=result["error"])
    log.info(
        "/quality/to-parquet subject=%s source=%s righe=%d bytes_in=%d bytes_out=%d",
        user.subject, "url" if body.url else "content",
        result["righe"], result["dimensione_csv"], result["dimensione_parquet"],
    )
    return Response(
        content=result["content"],
        media_type="application/vnd.apache.parquet",
        headers={"Content-Disposition": 'attachment; filename="dati.parquet"'},
    )


@router.post("/quality/xlsx-to-csv")
async def quality_xlsx_to_csv(
    body: BinaryIn,
    sheet: str | None = None,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict:
    """Convertitore binario (#157): XLSX → CSV, server-side, per REST/A2A.

    La UI converte gli XLSX client-side (SheetJS); questo porta la stessa capability
    lato server. Input binario via `content_base64` o `url`. Deterministico.
    Richiede l'extra `converters` (openpyxl): se assente → 501. Gli .xls legacy
    non sono supportati (→ 422 con messaggio chiaro).

    Args:
        sheet: nome del foglio da convertire (default: il primo/attivo).
    """
    data = await _resolve_bytes(body)
    result = xlsx_to_csv(data, sheet=sheet)
    if not result["ok"]:
        status = 501 if "openpyxl" in (result["error"] or "") else 422
        raise HTTPException(status_code=status, detail=result["error"])
    log.info(
        "/quality/xlsx-to-csv subject=%s source=%s foglio=%s righe=%d",
        user.subject, "url" if body.url else "base64", result["sheet"], result["righe"],
    )
    return result


@router.post("/quality/shapefile-to-geojson")
async def quality_shapefile_to_geojson(
    body: BinaryIn,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict:
    """Convertitore binario (#157): Shapefile.zip → GeoJSON (WGS84), server-side.

    La UI converte gli shapefile client-side (shpjs); questo porta la stessa
    capability lato server per REST/A2A. Riproietta in WGS84 leggendo il `.prj`.
    Input binario via `content_base64` o `url`. Richiede l'extra `converters`
    (pyshp/pyproj): se assente → 501. Guardia zip-bomb → 413.
    """
    data = await _resolve_bytes(body)
    result = shapefile_to_geojson(data)
    if not result["ok"]:
        if result.get("zipbomb"):
            raise HTTPException(status_code=413, detail=result["error"])
        status = 501 if ("pyshp" in (result["error"] or "") or "pyproj" in (result["error"] or "")) else 422
        raise HTTPException(status_code=status, detail=result["error"])
    log.info(
        "/quality/shapefile-to-geojson subject=%s source=%s features=%d crs=%s",
        user.subject, "url" if body.url else "base64",
        result["feature_count"], result["source_crs"],
    )
    return result


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


@router.post("/quality/metadata-schema-org")
async def quality_metadata_schema_org(
    body: MetadataIn,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict:
    """Genera lo scheletro schema.org/Dataset (JSON-LD) da un file.

    Gemello di `/quality/metadata` ma nel vocabolario schema.org (quello letto
    da Google Dataset Search), sugli stessi campi dedotti dal profilo del file.
    """
    text = await _resolve_input(body)
    geo = _is_geojson(text, (body.format or "").lower())
    profile = profile_geojson(text) if geo else profile_csv(text)
    log.info(
        "/quality/metadata-schema-org subject=%s tipo=%s source=%s",
        user.subject, "geojson" if geo else "csv", "url" if body.url else "content",
    )
    return generate_schema_org(
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
    """Valida una scheda DCAT-AP_IT o schema.org/Dataset: campi obbligatori,
    licenza aperta, punteggio FAIR.

    Si passa una scheda già pronta (`metadata`, l'output di /quality/metadata o
    /quality/metadata-schema-org — il vocabolario si riconosce dal campo
    `profilo`) oppure un file (content/url + campi editoriali) da cui generarla
    al volo, scegliendo il vocabolario con `vocabolario: "dcat"|"schema_org"`
    (default "dcat"). Restituisce `{validazione, metadata}`.
    """
    schema_org = (
        body.metadata.get("profilo") == "schema.org/Dataset" if body.metadata is not None
        else (body.vocabolario or "dcat").lower() == "schema_org"
    )
    if body.metadata is not None:
        meta = body.metadata
    else:
        text = await _resolve_input(body)
        geo = _is_geojson(text, (body.format or "").lower())
        profile = profile_geojson(text) if geo else profile_csv(text)
        genera = generate_schema_org if schema_org else generate_dcat
        meta = genera(
            profile, titolo=body.titolo, descrizione=body.descrizione,
            licenza=body.licenza, ente=body.ente, tema=body.tema,
            frequenza=body.frequenza, url=body.url,
        )
    log.info("/quality/validate subject=%s source=%s vocabolario=%s",
             user.subject, "metadata" if body.metadata is not None else "file",
             "schema_org" if schema_org else "dcat")
    valida = validate_schema_org if schema_org else validate_dcat
    return {"validazione": valida(meta), "metadata": meta}


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
