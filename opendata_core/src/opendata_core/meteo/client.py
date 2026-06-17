"""Open-Meteo forecast client (free, keyless). Dati: CC BY 4.0 (open-meteo.com)."""

from __future__ import annotations

import os
from typing import Any

import httpx

OPEN_METEO_LICENSE = "CC-BY-4.0 (open-meteo.com)"
DEFAULT_BASE_URL = os.getenv("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")
HTTP_TIMEOUT = float(os.getenv("OPEN_METEO_TIMEOUT", "20"))

# WMO weather code → etichetta sintetica + flag "outdoor-friendly".
_WMO: dict[int, tuple[str, bool]] = {
    0: ("sereno", True), 1: ("prevalentemente sereno", True), 2: ("parz. nuvoloso", True),
    3: ("coperto", True), 45: ("nebbia", False), 48: ("nebbia", False),
    51: ("pioviggine", False), 53: ("pioviggine", False), 55: ("pioviggine", False),
    61: ("pioggia debole", False), 63: ("pioggia", False), 65: ("pioggia forte", False),
    71: ("neve", False), 73: ("neve", False), 75: ("neve", False),
    80: ("rovesci", False), 81: ("rovesci", False), 82: ("rovesci forti", False),
    95: ("temporale", False), 96: ("temporale", False), 99: ("temporale", False),
}


class MeteoError(RuntimeError):
    """Open-Meteo non raggiungibile o risposta inattesa."""


def describe_weather(code: int | None) -> tuple[str, bool]:
    """(etichetta, outdoor_ok) per un codice WMO. Default prudente: outdoor_ok False."""
    if code is None:
        return ("n/d", False)
    return _WMO.get(int(code), ("variabile", False))


async def forecast(lat: float, lon: float, *, days: int = 3) -> dict[str, Any]:
    """Previsione giornaliera per (lat, lon). Ritorna {license, daily:[{date,tmax,tmin,precip,code,label,outdoor_ok}]}."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto",
        "forecast_days": max(1, min(int(days), 16)),
    }
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            r = await client.get(DEFAULT_BASE_URL, params=params)
            r.raise_for_status()
            payload = r.json()
    except httpx.HTTPError as exc:
        raise MeteoError(f"Open-Meteo non raggiungibile: {exc}") from exc

    daily = payload.get("daily") or {}
    dates = daily.get("time") or []
    codes = daily.get("weathercode") or []
    tmax = daily.get("temperature_2m_max") or []
    tmin = daily.get("temperature_2m_min") or []
    precip = daily.get("precipitation_sum") or []
    out = []
    for i, date in enumerate(dates):
        code = codes[i] if i < len(codes) else None
        label, outdoor_ok = describe_weather(code)
        out.append({
            "date": date,
            "tmax": tmax[i] if i < len(tmax) else None,
            "tmin": tmin[i] if i < len(tmin) else None,
            "precip": precip[i] if i < len(precip) else None,
            "code": code, "label": label, "outdoor_ok": outdoor_ok,
        })
    return {"license": OPEN_METEO_LICENSE, "daily": out}
