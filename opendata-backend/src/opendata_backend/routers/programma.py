"""POST /programma — scheda programmatica evidence-based (verticale PA).

Auth + rate limit come gli altri endpoint (R7, mai anonimo). Audit etico
append-only su `opendata.history`: query, fonti citate e sommario di ogni
scheda generata. L'audit è garantito quando il database è configurato; in
dev senza DATABASE_URL l'endpoint resta usabile e l'assenza è loggata.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends

from ..auth import ClerkUser
from ..db.repositories import history as history_repo
from ..db.repositories import users as users_repo
from ..orchestrator.programma import ProgrammaRequest, ProgrammaResponse
from ..shared.ratelimit import enforce_rate_limit
from ..state import session_holder

log = logging.getLogger("opendata-backend.programma")

router = APIRouter(tags=["programma"])


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

    try:
        resp = await sess.run_programma(req)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    await _audit(user, req, resp)
    log.info("programma generato: %s", _summary(resp))
    return resp
