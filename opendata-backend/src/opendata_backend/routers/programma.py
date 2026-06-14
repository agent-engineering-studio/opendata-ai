"""POST /programma — scheda programmatica evidence-based (verticale PA).

Auth + rate limit come gli altri endpoint (R7, mai anonimo). Audit etico
append-only su `opendata.history`: query, fonti citate e sommario di ogni
scheda generata. L'audit è garantito quando il database è configurato; in
dev senza DATABASE_URL l'endpoint resta usabile e l'assenza è loggata.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from fastapi.responses import StreamingResponse

from opendata_core.kg import KgClient

from ..auth import ClerkUser
from ..db.repositories import comuni as comuni_repo
from ..db.repositories import history as history_repo
from ..db.repositories import programma_cache as cache_repo
from ..db.repositories import users as users_repo
from ..orchestrator.programma import PROMPT_VERSION, ProgrammaRequest, ProgrammaResponse
from ..shared.ratelimit import enforce_rate_limit
from ..state import session_holder

log = logging.getLogger("opendata-backend.programma")

router = APIRouter(tags=["programma"])


async def _cache_key_for(req: ProgrammaRequest) -> tuple[str, int] | None:
    """Calcola (cache_key, knowledge_version) per la richiesta, o None se la
    cache è disabilitata (no DB o TTL=0)."""
    settings = session_holder.settings
    db = session_holder.database
    if db is None or settings is None or settings.programma_cache_ttl_days <= 0:
        return None
    async with db.session() as session:
        kv = await cache_repo.get_knowledge_version(session, req.cod_comune)
    key = cache_repo.compute_cache_key(
        cod_comune=req.cod_comune,
        tema=req.tema,
        cicli=req.cicli,
        modalita=req.modalita,
        knowledge_version=kv,
        prompt_version=PROMPT_VERSION,
    )
    return key, kv


async def _cache_lookup(cache_key: str) -> ProgrammaResponse | None:
    """Scheda fresca dalla cache (con da_cache=True), o None."""
    db = session_holder.database
    if db is None:
        return None
    async with db.session() as session:
        row = await cache_repo.get_fresh(session, cache_key, now=datetime.now(timezone.utc))
        if row is None:
            return None
        scheda_json = row.scheda_json
    resp = ProgrammaResponse.model_validate_json(scheda_json)
    resp.da_cache = True
    return resp


async def _cache_store(cache_key: str, knowledge_version: int, req: ProgrammaRequest,
                       resp: ProgrammaResponse) -> None:
    """Salva la scheda in cache (best-effort: un errore non rompe la risposta)."""
    settings = session_holder.settings
    db = session_holder.database
    if db is None or settings is None or settings.programma_cache_ttl_days <= 0:
        return
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.programma_cache_ttl_days)
    try:
        async with db.session() as session:
            await cache_repo.upsert(
                session,
                cache_key=cache_key,
                cod_comune=req.cod_comune,
                tema=req.tema,
                modalita=req.modalita,
                knowledge_version=knowledge_version,
                prompt_version=PROMPT_VERSION,
                scheda_json=resp.model_dump_json(),
                generato_il=resp.generato_il,
                expires_at=expires_at,
            )
            await session.commit()
    except Exception:
        log.warning("cache store fallito per %s (proseguo)", req.cod_comune)


def _analysis_summary_text(resp: ProgrammaResponse) -> str:
    """Testo sintetico dell'analisi da ingestionare nel KG (ricerca trasversale)."""
    lines = [f"Analisi del territorio — comune {resp.comune}"]
    if resp.zona:
        lines.append(f"zona: {resp.zona}")
    if resp.sintesi.strip():
        lines.append(f"\nSINTESI\n{resp.sintesi.strip()}")
    if resp.idee_sintesi.strip():
        lines.append(f"\nIDEE (lettura d'insieme)\n{resp.idee_sintesi.strip()}")
    proposte = [p.titolo for p in resp.proposte if not p.generatore]
    idee = [p.titolo for p in resp.proposte if p.generatore]
    if proposte:
        lines.append("\nProposte:\n- " + "\n- ".join(proposte))
    if idee:
        lines.append("\nIdee:\n- " + "\n- ".join(idee))
    return "\n".join(lines)


async def _push_analysis_to_kg(resp: ProgrammaResponse) -> None:
    """Ingestiona il riassunto dell'analisi nel KG, su namespace SEPARATO
    (`analisi-<cod>`), per la ricerca trasversale tra comuni. Best-effort e
    no-op se il KG non è configurato. Namespace distinto da `comune-<cod>` così
    l'agente KG non rilegge le analisi come evidenza (niente auto-citazione)."""
    settings = session_holder.settings
    if settings is None or not settings.enable_kg_analysis_push or not settings.kg_api_url:
        return
    try:
        namespace = f"{settings.kg_analysis_namespace_prefix}{resp.comune}"
        dest_dir = Path(settings.kg_upload_dir) / namespace
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{uuid.uuid4().hex}.txt"
        dest.write_text(_analysis_summary_text(resp), encoding="utf-8")
        async with KgClient(settings.kg_api_url) as kg:
            await kg.ingest(str(dest), namespace)
    except Exception:
        log.warning("push riassunto analisi nel KG fallito per %s (proseguo)", resp.comune)


async def _enrich_popolazione(req: ProgrammaRequest) -> None:
    """Arricchisce la richiesta con la popolazione del comune (anagrafica
    locale) → abilita la modalità macro per le città grandi. Best-effort: senza
    DB o senza anagrafica sincronizzata, la popolazione resta None.
    """
    db = session_holder.database
    if db is None:
        return
    try:
        async with db.session() as session:
            req.popolazione = await comuni_repo.get_popolazione(session, req.cod_comune)
    except Exception:
        log.warning("lookup popolazione fallito per %s (proseguo senza)", req.cod_comune)


def _summary(resp: ProgrammaResponse) -> str:
    n_voci = sum(len(v) for v in resp.swot.values())
    fonti = sorted({str(r.source) for r in resp.citazioni if r.source})
    return (
        f"programma {resp.comune}"
        + (f" zona={resp.zona}" if resp.zona else "")
        + f": {n_voci} voci SWOT, {len(resp.proposte)} proposte, "
        + f"{len(resp.citazioni)} citazioni ({', '.join(fonti) or 'nessuna fonte'})"
    )


async def _audit(user: ClerkUser, req: ProgrammaRequest, resp: ProgrammaResponse) -> None:
    """Append-only su opendata.history — best effort ma loggato se impossibile."""
    db = session_holder.database
    if db is None:
        log.warning("audit programma SALTATO: database non configurato (solo dev)")
        return
    async with db.session() as session:
        row = await users_repo.get_or_create(
            session, clerk_user_id=user.subject, email=user.email
        )
        await history_repo.append(
            session,
            user_id=row.id,
            query=f"/programma {json.dumps(req.model_dump(exclude_none=True), ensure_ascii=False)}",
            response_summary=_summary(resp),
        )
        await session.commit()


@router.post("/programma", response_model=ProgrammaResponse)
async def genera_programma(
    req: ProgrammaRequest,
    user: ClerkUser = Depends(enforce_rate_limit),  # noqa: B008
) -> ProgrammaResponse:
    """Genera la scheda SWOT + proposte per un comune, con citazioni risolvibili."""
    sess = session_holder.session
    if sess is None:
        raise HTTPException(status_code=503, detail="Orchestratore non inizializzato")
    settings = session_holder.settings
    if settings is not None and not settings.enable_programma:
        raise HTTPException(status_code=404, detail="Endpoint /programma disabilitato")
    if settings is not None:
        from ..config import check_territorio_scope

        try:
            check_territorio_scope(req.cod_comune, settings)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if settings is not None and not settings.enable_opencoesione:
        # Visto al primo collaudo: senza la fonte cuore la scheda esce vuota
        # (guardrail corretti, configurazione no) — rendiamolo diagnosticabile.
        log.warning(
            "/programma con ENABLE_OPENCOESIONE=false: la scheda uscirà povera o "
            "vuota — abilita la fonte nel .env (+ ENABLE_ISPRA/ENABLE_OSM consigliate)"
        )
    if settings is not None and req.modalita == "marketing" and not settings.enable_web:
        # Senza la fonte web il guardrail marketing (A)+(B) scarta ogni spunto
        # (manca il precedente esterno) — la sezione uscirà vuota.
        log.warning(
            "/programma modalita=marketing con ENABLE_WEB=false: gli spunti "
            "verranno scartati (manca l'ispirazione esterna) — abilita ENABLE_WEB "
            "(web-mcp + SearXNG) nel .env"
        )

    await _enrich_popolazione(req)
    ck = await _cache_key_for(req)
    if ck and not req.force_refresh:
        cached = await _cache_lookup(ck[0])
        if cached is not None:
            log.info("programma da cache: %s", _summary(cached))
            return cached

    try:
        resp = await sess.run_programma(req)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if ck:
        await _cache_store(ck[0], ck[1], req, resp)
    await _push_analysis_to_kg(resp)
    await _audit(user, req, resp)
    log.info("programma generato: %s", _summary(resp))
    return resp


@router.post("/programma/stream")
async def genera_programma_stream(
    req: ProgrammaRequest,
    user: ClerkUser = Depends(enforce_rate_limit),  # noqa: B008
) -> StreamingResponse:
    """Come /programma ma con eventi NDJSON di avanzamento granulari.

    Una riga JSON per evento: `status` (start/end per fonte e per la sintesi),
    `tool` (ogni chiamata MCP: nome strumento, start/end/error), `heartbeat`,
    poi un'unica riga `result` con la scheda completa.
    """
    sess = session_holder.session
    if sess is None:
        raise HTTPException(status_code=503, detail="Orchestratore non inizializzato")
    settings = session_holder.settings
    if settings is not None:
        from ..config import check_territorio_scope

        try:
            check_territorio_scope(req.cod_comune, settings)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not settings.enable_programma:
            raise HTTPException(status_code=404, detail="Endpoint /programma disabilitato")
        if not settings.enable_opencoesione:
            log.warning(
                "/programma/stream con ENABLE_OPENCOESIONE=false: scheda povera o vuota"
            )

    await _enrich_popolazione(req)
    ck = await _cache_key_for(req)

    async def _events():
        try:
            # Hit di cache: niente fan-out, un solo evento result immediato.
            if ck and not req.force_refresh:
                cached = await _cache_lookup(ck[0])
                if cached is not None:
                    await _audit(user, req, cached)
                    log.info("programma (stream) da cache: %s", _summary(cached))
                    yield json.dumps(
                        {"event": "result", "scheda": cached.model_dump(mode="json")},
                        ensure_ascii=False,
                    ) + "\n"
                    return
            async for ev in sess.run_programma_streaming(req):
                if ev.get("event") == "result":
                    resp = ProgrammaResponse.model_validate(ev["scheda"])
                    if ck:
                        await _cache_store(ck[0], ck[1], req, resp)
                    await _push_analysis_to_kg(resp)
                    await _audit(user, req, resp)
                    log.info("programma (stream) generato: %s", _summary(resp))
                yield json.dumps(ev, ensure_ascii=False) + "\n"
        except Exception as exc:  # mai un troncamento muto verso il client
            log.exception("/programma/stream failed")
            yield json.dumps(
                {"event": "error", "message": str(exc)}, ensure_ascii=False
            ) + "\n"

    return StreamingResponse(_events(), media_type="application/x-ndjson")
