"""Router /maturity — assessment maturità open-data di un ente (ODM 2025).

Tutti gli endpoint sono autenticati (Clerk) + rate-limited come gli altri.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import ClerkUser
from ..config import Settings, get_settings
from ..db.session import get_db_session
from ..maturity.markdown import build_scorecard_markdown
from ..maturity.service import build_ranking, build_scorecard, run_assessment
from ..shared.ratelimit import enforce_rate_limit

log = logging.getLogger("opendata-backend.maturity.router")

router = APIRouter(tags=["maturity"])


class AssessIn(BaseModel):
    entity: str
    base_url: str | None = None
    force: bool = False
    # Collega l'ente a un comune (codice ISTAT): i gap di dato del territorio
    # riducono l'Impact (anello valore⇄maturità) E abilitano il fallback sul
    # portale CKAN regionale quando dati.gov.it non ha i dataset del comune.
    istat_code: str | None = None
    # Nome del comune: usato per la risoluzione del portale (ricerca per nome /
    # portale regionale) oltre allo slug `entity`.
    comune_nome: str | None = None


@router.post("/maturity/assess")
async def assess(
    body: AssessIn,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    """Avvia/aggiorna l'assessment di un ente e ritorna la scorecard."""
    entity = body.entity.strip()
    if not entity:
        raise HTTPException(status_code=422, detail="campo 'entity' obbligatorio")
    return await run_assessment(
        session, entity=entity, base_url=body.base_url, settings=settings,
        force=body.force, istat_code=body.istat_code, comune_nome=body.comune_nome,
    )


@router.post("/maturity/assess/stream")
async def assess_stream(
    body: AssessIn,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> StreamingResponse:
    """Come /maturity/assess ma con eventi NDJSON di avanzamento granulari.

    Evita lo stato di "freeze" sulla valutazione: una riga JSON per evento
    (`status` start/end per fase: portale, analisi, punteggio, salvataggio;
    `heartbeat` mentre una fase è in corso), poi un'unica riga `result` con la
    scorecard completa.
    """
    entity = body.entity.strip()
    if not entity:
        raise HTTPException(status_code=422, detail="campo 'entity' obbligatorio")

    async def _events():
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        async def _run() -> dict[str, Any]:
            try:
                return await run_assessment(
                    session, entity=entity, base_url=body.base_url, settings=settings,
                    force=body.force, istat_code=body.istat_code, comune_nome=body.comune_nome,
                    emit=queue.put_nowait,
                )
            finally:
                queue.put_nowait(None)  # sentinel

        task = asyncio.create_task(_run())
        try:
            while True:
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=8.0)
                except asyncio.TimeoutError:
                    # Nessun cambio di fase entro 8s: heartbeat così la UI non
                    # sembra bloccata (l'harvest del portale può essere lento).
                    yield json.dumps({"event": "heartbeat"}, ensure_ascii=False) + "\n"
                    continue
                if ev is None:
                    break
                yield json.dumps(ev, ensure_ascii=False) + "\n"
            scorecard = await task
            yield json.dumps({"event": "result", "scorecard": scorecard}, ensure_ascii=False) + "\n"
        except Exception as exc:  # mai un troncamento muto verso il client
            log.exception("/maturity/assess/stream failed")
            if not task.done():
                task.cancel()
            yield json.dumps({"event": "error", "message": str(exc)}, ensure_ascii=False) + "\n"

    return StreamingResponse(_events(), media_type="application/x-ndjson")


@router.get("/maturity/entities/{entity_id}")
async def get_entity_scorecard(
    entity_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    """Scorecard dell'ente: 4 dimensioni, livello ODM, raccomandazioni, trend, mediana cluster."""
    scorecard = await build_scorecard(session, entity_id)
    if scorecard is None:
        raise HTTPException(status_code=404, detail="ente o assessment non trovato")
    return scorecard


@router.get("/maturity/entities/{entity_id}/scorecard.csv")
async def scorecard_csv(
    entity_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> Response:
    """Export CSV della scorecard di maturità dell'ente."""
    sc = await build_scorecard(session, entity_id)
    if sc is None:
        raise HTTPException(status_code=404, detail="ente o assessment non trovato")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["campo", "valore"])
    w.writerow(["ente", sc["entity"]["name"]])
    w.writerow(["livello", sc["level"]])
    w.writerow(["overall", sc["overall"]])
    for dim, val in sc["dimensions"].items():
        w.writerow([f"dimensione_{dim}", val])
    w.writerow(["n_datasets", sc.get("n_datasets")])
    w.writerow(["domanda_riuso_non_soddisfatta", (sc.get("unmet_reuse_demand") or {}).get("count", 0)])
    for r in sc.get("recommendations", []):
        w.writerow([f"raccomandazione_{r['code']}", r["message"]])
    return Response(
        content=buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="scorecard-{entity_id}.csv"'},
    )


@router.get("/maturity/entities/{entity_id}/scorecard.md")
async def scorecard_markdown(
    entity_id: int,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> Response:
    """Export Markdown embeddabile della scorecard (riepilogo + link).

    Pensato per essere incorporato in siti esterni (es. il portale istituzionale
    di un Comune). Quando l'ente non ha open data sufficienti, restituisce un
    disclaimer di raccomandazione con i vantaggi dell'open data, la guida
    operativa e i link alla documentazione di OpenData AI.
    """
    sc = await build_scorecard(session, entity_id)
    if sc is None:
        raise HTTPException(status_code=404, detail="ente o assessment non trovato")
    md = build_scorecard_markdown(sc, ui_base_url=settings.public_ui_base_url)
    return Response(
        content=md, media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'inline; filename="maturita-{entity_id}.md"'},
    )


@router.get("/maturity/ranking")
async def ranking(
    entity_type: str | None = Query(default=None, alias="type"),
    region: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    """Benchmark tra enti (filtrabile per type/regione) + mediana del cluster."""
    return await build_ranking(session, entity_type=entity_type, region=region)
