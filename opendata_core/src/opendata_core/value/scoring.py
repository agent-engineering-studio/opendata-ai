"""Stima del valore di un dataset secondo i 4 criteri dell'art. 14 Dir. (UE) 2019/1024.

Deterministico: socio-economico, platea/PMI, proventi (riuso commerciale),
combinabilità. L'overall è la media dei 4 (0–100). Il `reuse_score` (uso reale) è
iniettato dal backend e riportato a parte, NON entra nell'overall art. 14.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..maturity.models import MACHINE_READABLE, OPEN_FORMATS, DatasetInput
from ..maturity.hvd import match_hvd_category
from .combinability import combinability
from .models import ValueScore


def _open_format(ds: DatasetInput) -> bool:
    return bool({f.lower() for f in ds.formats} & OPEN_FORMATS)


def _machine_readable(ds: DatasetInput) -> bool:
    return bool({f.lower() for f in ds.formats} & MACHINE_READABLE)


def _fresh(ds: DatasetInput, as_of: datetime) -> bool:
    if ds.modified is None:
        return False
    m = ds.modified if ds.modified.tzinfo else ds.modified.replace(tzinfo=timezone.utc)
    return (as_of - m).days <= 730  # entro 2 anni


def _socioeconomic(ds: DatasetInput, hvd: str | None) -> float:
    # HVD = alto valore socio-economico per regolamento; tema + descrizione ricca rafforzano.
    score = 60.0 if hvd else 0.0
    if ds.theme:
        score += 20.0
    if ds.description and len(ds.description) >= 80:
        score += 20.0
    return min(100.0, score)


def _audience_sme(ds: DatasetInput) -> float:
    # Platea ampia / PMI: tanto più riusabile quanto più aperto e machine-readable.
    return min(100.0, 40.0 * ds.license_is_open + 35.0 * _open_format(ds) + 25.0 * _machine_readable(ds))


def _revenue(ds: DatasetInput, comb_score: float, fresh: bool) -> float:
    # Potenziale di riuso commerciale: machine-readable + licenza permissiva +
    # combinabilità + freschezza.
    return min(
        100.0,
        30.0 * _machine_readable(ds) + 30.0 * ds.license_is_open
        + 25.0 * (comb_score > 0) + 15.0 * fresh,
    )


def estimate_value(
    ds: DatasetInput, *, reuse_score: float | None = None, as_of: datetime | None = None
) -> ValueScore:
    """Stima il valore del dataset (art. 14). `reuse_score` opzionale (uso reale)."""
    now = as_of or datetime.now(timezone.utc)
    hvd = match_hvd_category(ds)
    comb = combinability(ds)

    socio = _socioeconomic(ds, hvd)
    audience = _audience_sme(ds)
    revenue = _revenue(ds, comb.score, _fresh(ds, now))
    overall = round((socio + audience + revenue + comb.score) / 4.0, 1)

    return ValueScore(
        socioeconomic=round(socio, 1),
        audience_sme=round(audience, 1),
        revenue=round(revenue, 1),
        combinability=comb.score,
        overall=overall,
        hvd_category=hvd,
        reuse_score=reuse_score,
    )
