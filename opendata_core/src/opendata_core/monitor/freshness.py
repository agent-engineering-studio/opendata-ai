"""Controllo di freshness — il dataset è aggiornato entro la cadenza dichiarata?

`check_freshness` confronta l'età dell'ultimo aggiornamento noto (es. header
HTTP `Last-Modified` della risorsa) con la cadenza dichiarata (`accrualPeriodicity`
DCAT-AP_IT: `ANNUAL`, `MONTHLY`, …). Senza cadenza dichiarata o senza una data di
riferimento non si può giudicare — `None`, mai un giudizio inventato. Una
tolleranza del 50% oltre la cadenza attesa evita falsi allarmi su pubblicazioni
appena in ritardo di pochi giorni.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .findings import _finding

# Cadenza dichiarata (vocabolario UE frequency / DCAT-AP_IT) → giorni attesi tra
# un aggiornamento e l'altro. None = non periodico o non giudicabile.
_PERIODICITA_GIORNI: dict[str, int | None] = {
    "DAILY": 1,
    "WEEKLY": 7,
    "BIWEEKLY": 14,
    "MONTHLY": 31,
    "QUARTERLY": 92,
    "BIENNIAL": 731,
    "ANNUAL": 366,
    "IRREG": None,
    "IRREGULAR": None,
    "CONT": None,
    "CONTINUOUS": None,
    "NEVER": None,
    "UNKNOWN": None,
}
_TOLLERANZA = 0.5  # 50% di margine oltre la cadenza dichiarata prima di segnalare


def check_freshness(
    periodicita: str | None,
    ultimo_aggiornamento_iso: str | None,
    ora_iso: str,
) -> dict[str, Any] | None:
    """Finding se il dataset risulta stantio, `None` se non giudicabile o aggiornato."""
    if not periodicita or not ultimo_aggiornamento_iso:
        return None
    giorni_attesi = _PERIODICITA_GIORNI.get(periodicita.strip().upper())
    if not giorni_attesi:
        return None
    try:
        ultimo = datetime.fromisoformat(ultimo_aggiornamento_iso)
        ora = datetime.fromisoformat(ora_iso)
    except ValueError:
        return None
    eta_giorni = (ora - ultimo).total_seconds() / 86400
    soglia = giorni_attesi * (1 + _TOLLERANZA)
    if eta_giorni <= soglia:
        return None
    livello = "alto" if eta_giorni > giorni_attesi * 2 else "medio"
    return _finding(
        livello, "stantio",
        f"Non aggiornato da {round(eta_giorni)} giorni (cadenza dichiarata: {periodicita}, "
        f"attesa ogni {giorni_attesi} giorni).",
    )
