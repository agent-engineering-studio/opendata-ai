"""Runner del monitoraggio schedulato — console-script `opendata-monitor` (#88).

Per ogni target attivo: scarica la risorsa (stessa validazione anti-SSRF del
proxy dataset), la ri-profila se è un CSV/GeoJSON, confronta con l'ultimo run
salvato via `opendata_core.monitor.run_checks`, persiste lo snapshot + il diff
e notifica (webhook sempre disponibile, email opt-in) solo se sono comparse
NUOVE segnalazioni rispetto al run precedente — niente spam quotidiano su un
problema già noto. Fail-safe per target: un target che fallisce non blocca gli
altri (stesso principio di `opendata-batch`).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from opendata_core.monitor import check_maturity_regression, diff_runs, run_checks
from opendata_core.quality import profile_csv, profile_geojson

from ..config import Settings
from ..db.repositories import maturity as maturity_repo
from ..db.repositories import monitor as repo
from ..db.territory_models import MonitorTarget
from ..routers.datasets import _validate_proxy_url
from .notify import build_email_body, build_notification_payload, send_email, send_webhook

log = logging.getLogger("opendata-backend.monitor.runner")

_FETCH_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
_MAX_FETCH_BYTES = 16 * 1024 * 1024  # 16 MB — coerente con /quality/*


async def _fetch(url: str, timeout_seconds: float) -> dict[str, Any]:
    """Scarica la risorsa; ritorna status/errore/last_modified/testo (best-effort)."""
    try:
        _validate_proxy_url(url)
    except HTTPException as exc:
        return {"status_code": None, "errore": str(exc.detail), "last_modified": None, "testo": None}

    timeout = httpx.Timeout(connect=timeout_seconds, read=timeout_seconds, write=timeout_seconds, pool=timeout_seconds)
    try:
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True,
            headers={"User-Agent": "opendata-ai/1.0 (+monitor)"},
        ) as client:
            resp = await client.get(url)
    except httpx.HTTPError as exc:
        return {"status_code": None, "errore": str(exc), "last_modified": None, "testo": None}

    last_modified = resp.headers.get("last-modified")
    testo = None
    if resp.status_code < 400:
        raw = resp.content[:_MAX_FETCH_BYTES]
        try:
            testo = raw.decode(resp.encoding or "utf-8", errors="replace")
        except LookupError:
            testo = raw.decode("utf-8", errors="replace")
    return {"status_code": resp.status_code, "errore": None, "last_modified": last_modified, "testo": testo}


def _last_modified_iso(header_value: str | None) -> str | None:
    if not header_value:
        return None
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(header_value)
        return dt.isoformat() if dt else None
    except (TypeError, ValueError):
        return None


def _profile_score(testo: str | None) -> float | None:
    """Punteggio qualità best-effort (CSV o GeoJSON); `None` se non profilabile."""
    if not testo or not testo.strip():
        return None
    stripped = testo.lstrip()[:4000]
    is_geo = stripped[:1] == "{" and '"type"' in stripped and any(
        k in stripped for k in ("FeatureCollection", '"Feature"', '"coordinates"')
    )
    try:
        profilo = profile_geojson(testo) if is_geo else profile_csv(testo)
    except Exception:  # noqa: BLE001 — un profilo fallito non deve bloccare il run
        return None
    return float(profilo.get("punteggio")) if profilo.get("punteggio") is not None else None


def _esito(findings: list[dict[str, Any]]) -> str:
    """Stessa regola di `run_checks`: critico se un finding è "alto"."""
    if any(f.get("livello") == "alto" for f in findings):
        return "critico"
    return "attenzione" if findings else "ok"


async def _notify_and_save(
    session: AsyncSession, target: MonitorTarget, *,
    settings: Settings, findings: list[dict[str, Any]], diff: dict[str, Any],
    quality_score: float | None,
) -> dict[str, Any]:
    """Coda comune dei check: notifica SOLO sui finding nuovi, poi persiste lo snapshot."""
    esito_run = {"esito": _esito(findings), "findings": findings}
    notificato = False
    if diff["nuovi"]:
        target_dict = {"id": target.id, "url": target.url, "entity_id": target.entity_id, "kind": target.kind}
        payload = build_notification_payload(target_dict, esito_run, diff)
        if target.webhook_url:
            notificato = await send_webhook(target.webhook_url, payload) or notificato
        if target.notify_email:
            corpo = build_email_body(target_dict, esito_run, diff)
            notificato = send_email(
                target.notify_email, f"[OpenData AI] Monitoraggio — {esito_run['esito']}", corpo, settings,
            ) or notificato

    await repo.save_run(
        session, target_id=target.id, esito=esito_run["esito"], findings=findings,
        diff=diff, quality_score=quality_score, notified=notificato,
    )
    log.info(
        "monitor target=%d kind=%s esito=%s nuovi=%d notificato=%s",
        target.id, target.kind, esito_run["esito"], len(diff["nuovi"]), notificato,
    )
    return {"target_id": target.id, "esito": esito_run["esito"], "nuovi": len(diff["nuovi"]), "notificato": notificato}


async def check_maturity_watch(
    session: AsyncSession, target: MonitorTarget, *, settings: Settings,
) -> dict[str, Any]:
    """Watch della scorecard ODM (#103): confronta gli ultimi due assessment dell'ente.

    Passivo e read-only: nessun fetch, scatta quando una nuova valutazione viene
    persistita (POST /maturity/assess o batch). Fail-safe: con 0-1 assessment il
    run è "ok" senza finding. Il no-renotify è lo stesso dei target dataset
    (`diff_runs` per codice): un calo già segnalato non genera nuove notifiche
    finché non rientra o non ne compare uno diverso.
    """
    assessments = await maturity_repo.last_two_assessments(session, target.entity_id)
    findings: list[dict[str, Any]] = []
    overall = None
    if assessments:
        att = assessments[0]
        overall = float(att.score_overall) if att.score_overall is not None else None
    if len(assessments) == 2:
        att, prec = assessments
        findings = check_maturity_regression(
            overall_attuale=float(att.score_overall) if att.score_overall is not None else None,
            overall_precedente=float(prec.score_overall) if prec.score_overall is not None else None,
            livello_attuale=att.level,
            livello_precedente=prec.level,
        )

    prec_run = await repo.latest_run(session, target.id)
    diff = diff_runs(prec_run.findings_jsonb if prec_run else None, findings)
    return await _notify_and_save(
        session, target, settings=settings, findings=findings, diff=diff, quality_score=overall,
    )


async def check_target(
    session: AsyncSession, target: MonitorTarget, *, settings: Settings, ora: datetime,
) -> dict[str, Any]:
    """Esegue un controllo completo su un target e persiste lo snapshot. Fail-safe."""
    if target.kind == "maturity":
        return await check_maturity_watch(session, target, settings=settings)

    dati = await _fetch(target.url, settings.monitor_http_timeout_seconds)
    punteggio_attuale = _profile_score(dati["testo"])

    prec = await repo.latest_run(session, target.id)
    punteggio_precedente = float(prec.quality_score) if prec and prec.quality_score is not None else None
    findings_precedenti = prec.findings_jsonb if prec else None

    esito_run = run_checks(
        periodicita=target.accrual_periodicity,
        ultimo_aggiornamento_iso=_last_modified_iso(dati["last_modified"]),
        ora_iso=ora.isoformat(),
        punteggio_attuale=punteggio_attuale,
        punteggio_precedente=punteggio_precedente,
        link_risultati=[{"url": target.url, "status_code": dati["status_code"], "errore": dati["errore"]}],
    )
    diff = diff_runs(findings_precedenti, esito_run["findings"])
    return await _notify_and_save(
        session, target, settings=settings, findings=esito_run["findings"], diff=diff,
        quality_score=punteggio_attuale,
    )


async def run_monitor(session: AsyncSession, *, settings: Settings) -> dict[str, Any]:
    """Esegue il controllo su tutti i target attivi. Un target che fallisce non blocca gli altri."""
    ora = datetime.now(timezone.utc)
    targets = await repo.list_active_targets(session)
    risultati: list[dict[str, Any]] = []
    for target in targets:
        try:
            risultati.append(await check_target(session, target, settings=settings, ora=ora))
            await session.commit()
        except Exception as exc:  # noqa: BLE001 — fail-safe: un target non blocca gli altri
            await session.rollback()
            log.exception("monitor target=%d fallito: %s", target.id, exc)
            risultati.append({"target_id": target.id, "esito": "errore", "nuovi": 0, "notificato": False})
    return {"n_target": len(targets), "risultati": risultati}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="opendata-monitor",
        description="Controlla freshness/qualità/link dei target monitorati e notifica i cambiamenti.",
    )
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    # Watch di maturità (#103): crea il target e esce, senza eseguire i controlli.
    # Le notifiche esterne restano dietro config esplicita (webhook/email qui sotto).
    parser.add_argument(
        "--add-maturity-watch", type=int, metavar="ENTITY_ID", default=None,
        help="crea un watch sulla scorecard di maturità dell'ente indicato ed esce",
    )
    parser.add_argument("--webhook-url", default=None, help="webhook da notificare (solo con --add-maturity-watch)")
    parser.add_argument("--notify-email", default=None, help="email da notificare (solo con --add-maturity-watch)")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("serve --database-url o la variabile DATABASE_URL")

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s", stream=sys.stderr,
    )

    from ..config import get_settings
    from ..db.session import create_database

    async def _run() -> None:
        db = create_database(args.database_url)
        try:
            async with db.sessionmaker() as session:
                if args.add_maturity_watch is not None:
                    row = await repo.create_target(
                        session, kind="maturity", entity_id=args.add_maturity_watch,
                        webhook_url=args.webhook_url, notify_email=args.notify_email,
                    )
                    await session.commit()
                    print(f"OK: watch maturità id={row.id} per entity_id={args.add_maturity_watch}")
                    return
                summary = await run_monitor(session, settings=get_settings())
            print(f"OK: monitor su {summary['n_target']} target")
        finally:
            await db.dispose()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
