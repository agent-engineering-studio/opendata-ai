"""Router /territory — report territoriale strutturato (modello canonico) + profilo.

Distinto da /territorio + /programma (fan-out conversazionale): qui il report nasce
dal data warehouse canonico (place/signal/investment/feature_store) + narrazione Sonnet.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import ClerkUser
from ..civic.checkin import open_checkin_thread
from ..civic.site import bundle_zip
from ..civic.site_service import build_site
from ..civic.snapshot import SnapshotError, create_snapshot
from ..config import Settings, get_settings
from ..db.session import get_db_session
from ..shared.ratelimit import enforce_rate_limit
from ..shared.scope import enforce_region_scope
from ..territory.service import build_report, get_profile

router = APIRouter(tags=["territory"])


class ReportIn(BaseModel):
    istat_code: str
    temi: list[str] | None = None
    anno_da: int | None = None
    anno_a: int | None = None


class SnapshotIn(BaseModel):
    snapshot_id: str
    sources_version: str = "auto"


@router.post("/territory/report")
async def territory_report(
    body: ReportIn,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    """Genera il report territoriale del comune (profilo, investimenti, segnali, gap) + narrazione."""
    istat = body.istat_code.strip()
    if not istat:
        raise HTTPException(status_code=422, detail="campo 'istat_code' obbligatorio")
    await enforce_region_scope(session, istat, settings)
    return await build_report(
        session, istat_code=istat, temi=body.temi,
        anno_da=body.anno_da, anno_a=body.anno_a, settings=settings,
    )


@router.get("/territory/{istat_code}/profile")
async def territory_profile(
    istat_code: str,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    """Profilo canonico cache-ato del comune (feature_store)."""
    await enforce_region_scope(session, istat_code.strip(), settings)
    profile = await get_profile(session, istat_code.strip())
    if profile is None:
        raise HTTPException(status_code=404, detail="profilo non disponibile: genera prima un report")
    return profile


@router.post("/territory/{istat_code}/snapshot", status_code=201)
async def snapshot_create(
    istat_code: str,
    body: SnapshotIn,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    """Crea uno snapshot civico versionato e apre il check-in community (se c'è un precedente)."""
    istat = istat_code.strip()
    await enforce_region_scope(session, istat, settings)
    try:
        snap = await create_snapshot(
            session, istat_code=istat, snapshot_id=body.snapshot_id.strip(),
            sources_version=body.sources_version,
        )
    except SnapshotError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    checkin = await open_checkin_thread(session, istat_code=istat, snapshot_id=snap.snapshot_id)
    await session.commit()
    return {"snapshot_id": snap.snapshot_id, "kpi_version": snap.kpi_version,
            "kpi": snap.kpi_jsonb, "checkin": checkin}


@router.post("/territory/{istat_code}/site/export")
async def site_export(
    istat_code: str,
    snapshot_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> Response:
    """Bundle zip del sito civico (pubblicabile su GitHub Pages/hosting comune)."""
    await enforce_region_scope(session, istat_code.strip(), settings)
    files = await build_site(session, istat_code=istat_code.strip(), snapshot_id=snapshot_id)
    if files is None:
        raise HTTPException(status_code=404, detail="nessuno snapshot: crea prima uno snapshot civico")
    data = bundle_zip(files)
    return Response(
        content=data, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="sito-civico-{istat_code}.zip"'},
    )


@router.get("/territory/{istat_code}/site/preview", response_class=HTMLResponse)
async def site_preview(
    istat_code: str,
    page: str = Query(default="index.html"),
    snapshot_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> HTMLResponse:
    """Anteprima HTML di una pagina del sito civico (default: Stato dell'arte)."""
    await enforce_region_scope(session, istat_code.strip(), settings)
    files = await build_site(session, istat_code=istat_code.strip(), snapshot_id=snapshot_id)
    if files is None:
        raise HTTPException(status_code=404, detail="nessuno snapshot: crea prima uno snapshot civico")
    if page not in files:
        raise HTTPException(status_code=404, detail=f"pagina {page} non disponibile")
    return HTMLResponse(content=files[page])
