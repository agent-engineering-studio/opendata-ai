"""Notifica webhook + email del monitoraggio — outward-facing, fail-safe (#88).

`send_webhook` è sempre disponibile (basta configurare l'URL sul target).
`send_email` è **opt-in esplicito**: se `settings.smtp_host` non è configurato,
l'invio è saltato (loggato, non un errore) — coerente col principio "le
notifiche esterne sono dietro config esplicita". Nessuna dipendenza nuova:
`smtplib`/`email` sono libreria standard.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Any

import httpx
from fastapi import HTTPException

from ..config import Settings
from ..routers.datasets import _validate_proxy_url

log = logging.getLogger("opendata-backend.monitor.notify")

_WEBHOOK_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)


async def send_webhook(url: str, payload: dict[str, Any]) -> bool:
    """POST JSON al webhook configurato. Fail-safe: un errore non solleva, ritorna False.

    Stessa validazione anti-SSRF della risorsa monitorata: un `webhook_url`
    salvato su un target non deve poter raggiungere la rete interna.
    """
    try:
        _validate_proxy_url(url)
    except HTTPException as exc:
        log.warning("webhook %s rifiutato: %s", url, exc.detail)
        return False
    try:
        async with httpx.AsyncClient(timeout=_WEBHOOK_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code >= 400:
            log.warning("webhook %s risposta %d", url, resp.status_code)
            return False
        return True
    except httpx.HTTPError as exc:
        log.warning("webhook %s fallito: %s", url, exc)
        return False


def send_email(to_addr: str, subject: str, body: str, settings: Settings) -> bool:
    """Invia una email via SMTP. Opt-in: senza `smtp_host` configurato, salta (True-safe log, non blocca).

    Ritorna True se inviata, False se saltata (non configurata) o fallita —
    mai un'eccezione: un problema di notifica non deve interrompere il run.
    """
    if not settings.smtp_host or not settings.smtp_from:
        log.info("email a %s saltata: SMTP non configurato (opt-in)", to_addr)
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_addr
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_user and settings.smtp_password:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        return True
    except (OSError, smtplib.SMTPException) as exc:
        log.warning("email a %s fallita: %s", to_addr, exc)
        return False


def build_notification_payload(
    target: dict[str, Any], run_result: dict[str, Any], diff: dict[str, Any],
) -> dict[str, Any]:
    """Corpo condiviso webhook/email: target, esito, finding, cosa è cambiato."""
    return {
        "target": {
            "id": target.get("id"), "url": target.get("url"),
            "entity_id": target.get("entity_id"), "kind": target.get("kind", "dataset"),
        },
        "esito": run_result["esito"],
        "findings": run_result["findings"],
        "diff": diff,
    }


def build_email_body(target: dict[str, Any], run_result: dict[str, Any], diff: dict[str, Any]) -> str:
    risorsa = target.get("url") or f"scorecard di maturità (ente {target.get('entity_id')})"
    righe = [
        f"Monitoraggio OpenData AI — esito: {run_result['esito'].upper()}",
        f"Risorsa: {risorsa}",
        "",
    ]
    if diff.get("nuovi"):
        righe.append("Nuove segnalazioni:")
        righe += [f"  - [{f['livello']}] {f['messaggio']}" for f in diff["nuovi"]]
    if diff.get("risolti"):
        righe.append("Risolte rispetto all'ultimo controllo:")
        righe += [f"  - {codice}" for codice in diff["risolti"]]
    if not diff.get("nuovi") and not diff.get("risolti"):
        righe.append("Nessun cambiamento rispetto all'ultimo controllo.")
    return "\n".join(righe)
