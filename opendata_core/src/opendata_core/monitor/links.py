"""Controllo dei link — le risorse rispondono (HTTP 200, non 404/410/timeout)?

`check_links` prende in ingresso l'ESITO già raccolto di ogni richiesta (status
code o errore di rete) — non fa I/O: il fetch (con la stessa validazione
anti-SSRF di `_validate_proxy_url`) è responsabilità del runner. Così il motore
resta puro e testabile offline.
"""

from __future__ import annotations

from typing import Any, TypedDict

from .findings import _finding


class RisultatoLink(TypedDict, total=False):
    url: str
    status_code: int | None
    errore: str | None


def check_links(risultati: list[RisultatoLink]) -> list[dict[str, Any]]:
    """Finding per ogni link irraggiungibile o rotto; lista vuota se tutti ok."""
    findings: list[dict[str, Any]] = []
    for r in risultati:
        url = r.get("url") or "<url sconosciuto>"
        errore = r.get("errore")
        status = r.get("status_code")
        if errore:
            findings.append(_finding("alto", "link_irraggiungibile", f"{url}: {errore}"))
        elif status is not None and status >= 400:
            livello = "alto" if status in (404, 410) else "medio"
            findings.append(_finding(livello, "link_rotto", f"{url}: HTTP {status}"))
    return findings
