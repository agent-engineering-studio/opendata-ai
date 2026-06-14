"""Endpoint /territorio/* — selezione zona via tag OSM per la UI (spec 06).

La UI non parla con gli MCP (R13): il backend importa direttamente
`opendata_core.osm.zones` (shared lib, nessun hop MCP). Cache Redis 24h —
le zone di un comune cambiano raramente e l'istanza Overpass pubblica
throttla — sopra la TTLCache in-process del core.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.params import Depends

from opendata_core.kg import KgClient, KgError
from opendata_core.osm import zones
from opendata_core.osm.zones import ZONA_TIPI, OverpassError

from ..auth import ClerkUser
from ..cache.store import cache_get, cache_set
from ..config import check_territorio_scope, get_settings, province_scope
from ..db.repositories import documenti as documenti_repo
from ..db.repositories import programma_cache as cache_repo
from ..shared.ratelimit import enforce_rate_limit
from ..state import session_holder

_ALLOWED_EXT = {".pdf", ".docx", ".txt"}

log = logging.getLogger("opendata-backend.territorio")

router = APIRouter(prefix="/territorio", tags=["territorio"])

_TTL = 24 * 3600


def _key(*parts: str) -> str:
    raw = "|".join(p.lower().strip() for p in parts).encode()
    return "od:territorio:" + hashlib.sha1(raw).hexdigest()


@router.get("/comuni")
async def cerca_comuni(
    q: str = Query(min_length=2, max_length=80, description="Nome comune, anche parziale"),
    user: ClerkUser = Depends(enforce_rate_limit),  # noqa: B008, ARG001
) -> dict:
    """Autocomplete comune → codice ISTAT (dai confini amministrativi OSM)."""
    scope = province_scope(get_settings())
    key = _key("comuni", q, ",".join(sorted(scope)))
    cached = await cache_get(key)
    if cached is not None:
        return cached
    try:
        results = await zones.lookup_comune(q)
    except OverpassError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if scope:
        # Ambito territoriale (es. produzione = Puglia): l'autocomplete
        # propone solo comuni delle province ammesse.
        results = [r for r in results if (r.get("ref_istat") or "")[:3] in scope]
    payload = {"results": results, "count": len(results)}
    await cache_set(key, payload, ttl_seconds=_TTL)
    return payload


@router.get("/confine")
async def confine_comune(
    osm_id: str = Query(
        pattern=r"^(relation|way)/\d+$",
        description="OSM id del confine, es. 'relation/44915' (da /territorio/comuni)",
    ),
    cod_comune: str | None = Query(
        default=None, pattern=r"^\d{6}$", description="Codice ISTAT per il controllo d'ambito"
    ),
    user: ClerkUser = Depends(enforce_rate_limit),  # noqa: B008, ARG001
) -> dict:
    """Geometria GeoJSON del confine dell'INTERO comune (per la mappa).

    Analisi a livello comunale: la mappa mostra solo il comune, non le zone.
    """
    if cod_comune:
        try:
            check_territorio_scope(cod_comune, get_settings())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    key = _key("confine", osm_id)
    cached = await cache_get(key)
    if cached is not None:
        return cached
    osm_type, _, oid = osm_id.partition("/")
    try:
        feature = await zones.get_zone(osm_type, oid)
    except OverpassError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not feature:
        raise HTTPException(status_code=404, detail=f"Confine non trovato per {osm_id}")
    payload = {"osm_id": osm_id, "feature": feature}
    await cache_set(key, payload, ttl_seconds=_TTL)
    return payload


# ─────────────────────────── documenti PA (F2) ──────────────────────────────


def _doc_to_dict(doc) -> dict:
    return {
        "id": doc.id,
        "cod_comune": doc.cod_comune,
        "filename": doc.filename,
        "stato": doc.stato,
        "pagine": doc.pagine,
        "mime_type": doc.mime_type,
        "kg_document_id": doc.kg_document_id,
        "errore": doc.errore,
        "caricato_il": doc.caricato_il.isoformat() if doc.caricato_il else None,
    }


@router.post("/documenti")
async def carica_documento(
    cod_comune: str = Form(pattern=r"^\d{6}$"),  # noqa: B008
    file: UploadFile = File(...),  # noqa: B008
    user: ClerkUser = Depends(enforce_rate_limit),  # noqa: B008
) -> dict:
    """Carica un PDF/DOCX/TXT della PA e lo ingestiona nel KG (namespace del
    comune). Registra i metadati e invalida la cache analisi del comune."""
    settings = get_settings()
    try:
        check_territorio_scope(cod_comune, settings)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not settings.kg_api_url:
        raise HTTPException(status_code=503, detail="Knowledge Graph non configurato (KG_API_URL)")
    db = session_holder.database
    if db is None:
        raise HTTPException(status_code=503, detail="Database non configurato")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(
            status_code=422, detail=f"Estensione {ext or '?'} non ammessa: {', '.join(sorted(_ALLOWED_EXT))}"
        )
    data = await file.read()
    if len(data) > settings.documenti_max_bytes:
        raise HTTPException(status_code=413, detail="File troppo grande")
    if not data:
        raise HTTPException(status_code=422, detail="File vuoto")

    namespace = f"{settings.kg_namespace_prefix}{cod_comune}"
    sha = hashlib.sha256(data).hexdigest()
    # Volume CONDIVISO backend↔KG: scrivi qui, poi passa il path al KG.
    dest_dir = Path(settings.kg_upload_dir) / namespace
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid.uuid4().hex}-{Path(file.filename or 'doc').name}"
    dest.write_bytes(data)

    async with db.session() as session:
        doc = await documenti_repo.create(
            session, cod_comune=cod_comune, filename=file.filename or dest.name,
            kg_namespace=namespace, sha256=sha, mime_type=file.content_type,
            caricato_da=user.subject, stato="in_ingest",
        )
        await session.commit()
        doc_id = doc.id

    kg_doc_id: str | None = None
    pagine: int | None = None
    stato, errore = "ingerito", None
    try:
        async with KgClient(settings.kg_api_url) as kg:
            res = await kg.ingest(str(dest), namespace)
        kg_doc_id = res.get("document_id")
        pagine = res.get("pages") or res.get("total_pages") or res.get("page_count")
    except KgError as exc:
        stato, errore = "errore", str(exc)[:500]
        log.warning("ingest KG fallito per %s: %s", file.filename, exc)

    async with db.session() as session:
        doc = await documenti_repo.get(session, doc_id)
        doc.kg_document_id, doc.pagine, doc.stato, doc.errore = kg_doc_id, pagine, stato, errore
        if stato == "ingerito":
            # la conoscenza del comune è cambiata → invalida la cache analisi
            await cache_repo.bump_knowledge_version(session, cod_comune)
        await session.commit()
        payload = _doc_to_dict(doc)
    return payload


@router.get("/documenti")
async def lista_documenti(
    cod_comune: str = Query(pattern=r"^\d{6}$"),
    user: ClerkUser = Depends(enforce_rate_limit),  # noqa: B008, ARG001
) -> dict:
    """Documenti del comune ingeriti nel KG (file manager)."""
    db = session_holder.database
    if db is None:
        return {"documenti": []}
    async with db.session() as session:
        rows = await documenti_repo.list_by_comune(session, cod_comune)
        return {"documenti": [_doc_to_dict(r) for r in rows]}


@router.delete("/documenti/{doc_id}")
async def elimina_documento(
    doc_id: int,
    user: ClerkUser = Depends(enforce_rate_limit),  # noqa: B008, ARG001
) -> dict:
    """Rimuove il documento dal KG e dal registro, invalidando la cache."""
    settings = get_settings()
    db = session_holder.database
    if db is None:
        raise HTTPException(status_code=503, detail="Database non configurato")
    async with db.session() as session:
        doc = await documenti_repo.get(session, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="Documento non trovato")
        cod_comune, kg_document_id = doc.cod_comune, doc.kg_document_id

    if kg_document_id and settings.kg_api_url:
        try:
            async with KgClient(settings.kg_api_url) as kg:
                await kg.delete_document(kg_document_id)
        except KgError as exc:
            # non blocchiamo la rimozione dal registro: logghiamo soltanto
            log.warning("delete KG fallito per doc %s: %s", doc_id, exc)

    async with db.session() as session:
        doc = await documenti_repo.get(session, doc_id)
        if doc is not None:
            await documenti_repo.delete(session, doc)
        await cache_repo.bump_knowledge_version(session, cod_comune)
        await session.commit()
    return {"ok": True, "id": doc_id}


@router.get("/zone")
async def lista_zone(
    cod_comune: str = Query(pattern=r"^\d{6}$", description="Codice ISTAT, es. 072006"),
    tipo: str = Query(description=f"Uno tra: {', '.join(ZONA_TIPI)}"),
    comune_nome: str | None = Query(
        default=None, max_length=80,
        description="Nome del comune — abilita il fallback Nominatim",
    ),
    user: ClerkUser = Depends(enforce_rate_limit),  # noqa: B008, ARG001
) -> dict:
    """Zone candidate di un tipo dentro il comune, con geometrie GeoJSON.

    Il payload dichiara il `fallback_level` (1 = tag match, 2 = Nominatim,
    3 = niente: la UI degrada all'analisi a livello comune).
    """
    if tipo not in ZONA_TIPI:
        raise HTTPException(
            status_code=422,
            detail=f"tipo {tipo!r} non valido. Valori ammessi: {', '.join(ZONA_TIPI)}",
        )
    try:
        check_territorio_scope(cod_comune, get_settings())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    key = _key("zone", cod_comune, tipo, comune_nome or "")
    cached = await cache_get(key)
    if cached is not None:
        return cached
    try:
        payload = await zones.list_zones(cod_comune, tipo, comune_nome=comune_nome)
    except OverpassError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    await cache_set(key, payload, ttl_seconds=_TTL)
    return payload
