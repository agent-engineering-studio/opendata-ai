"""Async HTTP client for the OpenCoesione API (Italian cohesion-policy projects).

API root: https://opencoesione.gov.it/it/api (plain JSON; resources progetti,
soggetti, aggregati, temi, nature, territori, programmi). See ``mapping.py`` for
every behaviour verified during discovery — most importantly:

  - unknown query params are silently ignored → filters are whitelisted here;
  - territorial filtering uses slugs ("bari-comune"), never ISTAT codes; the
    /territori resource resolves ISTAT codes to slugs (``cod_com=72006``);
  - the server throttles aggressively (HTTP 429 with a JSON ``detail`` telling
    how many seconds to wait) → retry with the suggested backoff;
  - /aggregati/territori/{slug}.json returns territory-wide totals broken down
    by state/theme and accepts ``ciclo_programmazione`` — so the funding
    capacity indicator costs ONE request instead of paginating projects.

Licence of API data: CC BY-SA 3.0 — every public method returns a resolvable
``source_url`` so callers can cite it.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

import httpx
from cachetools import TTLCache

from .mapping import (
    AGGREGATI_FILTERS,
    LICENZA_API,
    NATURE,
    PROGETTI_FILTERS,
    SOGGETTI_FILTERS,
    STATI,
    STATI_CONCLUSI,
    TEMI,
    comune_code_int,
    normalize_ciclo,
    normalize_slug_value,
    parse_amount,
)
from .models import FundingCapacity, ProjectSummary, StatoBreakdown, Territorio

DEFAULT_TIMEOUT = float(os.getenv("OPENCOESIONE_HTTP_TIMEOUT", "60"))
DEFAULT_BASE_URL = os.getenv("OPENCOESIONE_BASE_URL", "https://opencoesione.gov.it/it/api")
USER_AGENT = os.getenv(
    "OPENCOESIONE_USER_AGENT",
    "opencoesione-mcp-server/0.1 (+https://github.com/agent-engineering-studio)",
)
CACHE_TTL = int(os.getenv("OPENCOESIONE_CACHE_TTL_SECONDS", "3600"))
CACHE_MAXSIZE = int(os.getenv("OPENCOESIONE_CACHE_MAXSIZE", "512"))
#: page_size is capped server-side at 500 (verified: page_size=1000 → 500).
MAX_PAGE_SIZE = 500
MAX_RETRIES = 4
#: Never honour a throttle suggestion longer than this (seconds). Il server
#: dice esattamente quando torna capacità ("Expected available in N seconds",
#: visto live fino a 43s a throttle accumulato): aspettare batte fallire —
#: il cap serve solo contro suggerimenti assurdi.
MAX_THROTTLE_WAIT = float(os.getenv("OPENCOESIONE_MAX_THROTTLE_WAIT", "90"))

_THROTTLE_SECONDS = re.compile(r"(\d+)\s*second")

log = logging.getLogger("opendata-core.opencoesione")


class OpenCoesioneError(RuntimeError):
    """Raised when the OpenCoesione endpoint returns an unexpected payload or HTTP error."""


def _normalize_base(base_url: str | None) -> str:
    base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    return base


class OpenCoesioneClient:
    """Thin async wrapper around the OpenCoesione JSON API.

    Usage:
        async with OpenCoesioneClient() as c:
            cap = await c.funding_capacity("072006")
    """

    # Shared across instances: territory lookups and aggregates are stable
    # enough that subsequent tool calls in the same process should benefit.
    _cache: TTLCache = TTLCache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)

    def __init__(self, timeout: float = DEFAULT_TIMEOUT, base_url: str | None = None) -> None:
        self._timeout = timeout
        self._base = _normalize_base(base_url)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "OpenCoesioneClient":
        self._client = httpx.AsyncClient(
            base_url=self._base,
            timeout=self._timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ────────────────────────────── core HTTP ──────────────────────────────

    def source_url(self, path: str, params: dict[str, Any] | None = None) -> str:
        """Resolvable URL of a request — for the `sources` block of every output."""
        url = httpx.URL(self._base + "/" + path.lstrip("/"))
        if params:
            url = url.copy_merge_params(dict(sorted(params.items())))
        return str(url)

    async def _get_json(
        self, path: str, *, params: dict[str, Any] | None = None, cache: bool = True
    ) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("OpenCoesioneClient must be used as an async context manager")
        key = (self._base, path, tuple(sorted((params or {}).items())))
        if cache and key in self._cache:
            return self._cache[key]  # type: ignore[return-value]

        url = self.source_url(path, params)
        last_detail = ""
        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._client.get("/" + path.lstrip("/"), params=params)
            except httpx.HTTPError as exc:
                log.error("OpenCoesione transport error GET %s: %s", url, exc)
                raise OpenCoesioneError(f"Transport error on GET {path}: {exc}") from exc

            if resp.status_code == 429:
                # Body: {"detail": "… Expected available in N second(s)."}
                try:
                    last_detail = str(resp.json().get("detail", ""))
                except ValueError:
                    last_detail = resp.text[:200]
                m = _THROTTLE_SECONDS.search(last_detail)
                delay = min(float(m.group(1)) if m else 2.0 ** (attempt + 1), MAX_THROTTLE_WAIT)
                log.warning("OpenCoesione throttled on %s — retrying in %.1fs", url, delay)
                await asyncio.sleep(delay)
                continue
            if resp.status_code >= 500 and attempt < MAX_RETRIES - 1:
                delay = 2.0**attempt
                log.warning("OpenCoesione HTTP %s on %s — retrying in %.1fs",
                            resp.status_code, url, delay)
                await asyncio.sleep(delay)
                continue
            if resp.status_code == 404:
                raise OpenCoesioneError(
                    f"Not found: {url} — verifica lo slug del territorio o il CLP del progetto."
                )
            if resp.status_code >= 400:
                snippet = resp.text[:300].replace("\n", " ")
                raise OpenCoesioneError(f"HTTP {resp.status_code} on GET {path}: {snippet}")

            try:
                payload = resp.json()
            except ValueError as exc:
                raise OpenCoesioneError(
                    f"Non-JSON response from {path}: {resp.text[:300]}"
                ) from exc
            if cache:
                self._cache[key] = payload
            return payload

        raise OpenCoesioneError(
            f"Throttled by OpenCoesione after {MAX_RETRIES} attempts on {url}: {last_detail}"
        )

    # ─────────────────────────── territory resolution ───────────────────────

    async def resolve_territorio(
        self,
        *,
        cod_comune: str | int | None = None,
        cod_provincia: str | int | None = None,
        cod_regione: str | int | None = None,
        nome: str | None = None,
        tipo: str | None = None,
    ) -> Territorio | None:
        """Resolve an ISTAT code (or a name) to the /territori record with its slug.

        ISTAT codes are matched as integers (the API stores ``cod_com=72006``
        for "072006"). Returns None when nothing matches.
        """
        params: dict[str, Any] = {}
        if cod_comune is not None:
            params["cod_com"] = comune_code_int(cod_comune)
            params["tipo"] = "C"
        elif cod_provincia is not None:
            params["cod_prov"] = comune_code_int(cod_provincia)
            params["tipo"] = "P"
        elif cod_regione is not None:
            params["cod_reg"] = comune_code_int(cod_regione)
            params["tipo"] = "R"
        elif nome:
            params["denominazione"] = nome.strip()
            if tipo:
                params["tipo"] = tipo.strip().upper()
        else:
            raise ValueError("Serve almeno uno tra cod_comune/cod_provincia/cod_regione/nome.")

        payload = await self._get_json("territori.json", params=params)
        results = payload.get("results") or []
        if not results:
            return None
        if nome and len(results) > 1:
            # Prefer the exact (case-insensitive) name match over substring hits.
            exact = [r for r in results if str(r.get("denominazione", "")).lower() == nome.lower()]
            if exact:
                results = exact
        return Territorio(**{k: results[0][k] for k in Territorio.model_fields})

    async def _territorio_slug(
        self,
        territorio: str | None,
        cod_comune: str | int | None,
        cod_provincia: str | int | None,
        cod_regione: str | int | None,
    ) -> str | None:
        """Slug from an explicit slug or any ISTAT code; None when nothing was given."""
        if territorio:
            return territorio.strip().lower()
        if cod_comune is None and cod_provincia is None and cod_regione is None:
            return None
        t = await self.resolve_territorio(
            cod_comune=cod_comune, cod_provincia=cod_provincia, cod_regione=cod_regione
        )
        if t is None:
            given = cod_comune or cod_provincia or cod_regione
            raise OpenCoesioneError(
                f"Nessun territorio OpenCoesione per il codice ISTAT {given!r} — "
                "verifica il codice (es. comune '072006')."
            )
        return t.slug

    # ────────────────────────────── projects ────────────────────────────────

    @staticmethod
    def _slim_project(rec: dict[str, Any]) -> ProjectSummary:
        return ProjectSummary(
            clp=rec.get("cod_locale_progetto", ""),
            titolo=rec.get("oc_titolo_progetto") or None,
            tema=rec.get("oc_tema_sintetico") or None,
            stato=rec.get("oc_stato_progetto") or None,
            ciclo=rec.get("oc_descr_ciclo") or None,
            finanziamento_totale=parse_amount(rec.get("oc_finanz_tot_pub_netto")),
            pagamenti=parse_amount(rec.get("tot_pagamenti")),
            percentuale_avanzamento=rec.get("percentuale_avanzamento") or None,
            soggetti=rec.get("soggetti") or [],
            territori=rec.get("territori") or [],
            url=rec.get("url") or None,
        )

    def _paged_params(self, limit: int, offset: int) -> tuple[dict[str, Any], int]:
        limit = max(1, min(int(limit), MAX_PAGE_SIZE))
        offset = max(0, int(offset))
        if offset % limit:
            raise ValueError(
                f"offset ({offset}) deve essere un multiplo di limit ({limit}): "
                "l'API OpenCoesione pagina per pagine, non per offset libero."
            )
        page = offset // limit + 1
        return {"page_size": limit, "page": page}, limit

    async def search_projects(
        self,
        *,
        territorio: str | None = None,
        cod_comune: str | int | None = None,
        cod_provincia: str | int | None = None,
        cod_regione: str | int | None = None,
        tema: str | None = None,
        natura: str | None = None,
        stato: str | None = None,
        ciclo: str | None = None,
        fonte: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search /progetti with the verified filters; territorial scope via ISTAT code or slug.

        Returns ``{total, has_more, next_offset, results, source_url, licenza}``
        with slim ``ProjectSummary`` dicts in ``results``.
        """
        params, limit = self._paged_params(limit, offset)
        slug = await self._territorio_slug(territorio, cod_comune, cod_provincia, cod_regione)
        if slug:
            params["territorio"] = slug
        if tema:
            params["tema"] = normalize_slug_value(tema, TEMI, "Tema")
        if natura:
            params["natura"] = normalize_slug_value(natura, NATURE, "Natura")
        if stato:
            norm_stato = stato.strip().lower().replace("-", "_").replace(" ", "_")
            if norm_stato not in STATI:
                raise ValueError(f"Stato {stato!r} non valido. Valori ammessi: {', '.join(STATI)}")
            params["stato"] = norm_stato
        if ciclo:
            params["ciclo_programmazione"] = normalize_ciclo(ciclo)
        if fonte:
            params["fonte"] = fonte.strip()
        assert set(params) <= PROGETTI_FILTERS | {"page", "page_size"}

        payload = await self._get_json("progetti.json", params=params)
        total = int(payload.get("count") or 0)
        results = [self._slim_project(r).model_dump() for r in payload.get("results") or []]
        next_offset = offset + limit
        return {
            "total": total,
            "has_more": payload.get("next") is not None,
            "next_offset": next_offset if payload.get("next") is not None else None,
            "results": results,
            "facets": payload.get("facet_counts") or {},
            "source_url": self.source_url("progetti.json", params),
            "licenza": LICENZA_API,
        }

    async def get_project(self, clp: str) -> dict[str, Any]:
        """Full detail record for a project by its CLP (codice locale progetto)."""
        clp_norm = clp.strip().lower()
        if not clp_norm:
            raise ValueError("CLP vuoto.")
        path = f"progetti/{clp_norm}.json"
        payload = await self._get_json(path)
        payload["source_url"] = self.source_url(path)
        payload["licenza"] = LICENZA_API
        return payload

    # ────────────────────────────── soggetti ────────────────────────────────

    async def search_soggetti(
        self,
        *,
        territorio: str | None = None,
        cod_comune: str | int | None = None,
        cod_provincia: str | int | None = None,
        cod_regione: str | int | None = None,
        ruolo: str | None = None,
        tema: str | None = None,
        natura: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search /soggetti (implementing bodies etc.) by territory/role/theme/nature.

        Note (discovery): the API does NOT support free-text search on the
        denominazione — unknown params are silently ignored, so none is sent.
        """
        params, limit = self._paged_params(limit, offset)
        slug = await self._territorio_slug(territorio, cod_comune, cod_provincia, cod_regione)
        if slug:
            params["territorio"] = slug
        if ruolo:
            params["ruolo"] = ruolo.strip().lower()
        if tema:
            params["tema"] = normalize_slug_value(tema, TEMI, "Tema")
        if natura:
            params["natura"] = normalize_slug_value(natura, NATURE, "Natura")
        assert set(params) <= SOGGETTI_FILTERS | {"page", "page_size"}

        payload = await self._get_json("soggetti.json", params=params)
        return {
            "total": int(payload.get("count") or 0),
            "has_more": payload.get("next") is not None,
            "next_offset": offset + limit if payload.get("next") is not None else None,
            "results": payload.get("results") or [],
            "source_url": self.source_url("soggetti.json", params),
            "licenza": LICENZA_API,
        }

    # ────────────────────────────── aggregates ──────────────────────────────

    async def territorial_aggregates(
        self,
        *,
        territorio: str | None = None,
        cod_comune: str | int | None = None,
        cod_provincia: str | int | None = None,
        cod_regione: str | int | None = None,
        ciclo: str | None = None,
    ) -> dict[str, Any]:
        """Programmed/paid resources for a territory (totals + per-state/theme/year)."""
        slug = await self._territorio_slug(territorio, cod_comune, cod_provincia, cod_regione)
        if not slug:
            raise ValueError("Serve un territorio: slug oppure codice ISTAT.")
        params: dict[str, Any] = {}
        if ciclo:
            params["ciclo_programmazione"] = normalize_ciclo(ciclo)
        assert set(params) <= AGGREGATI_FILTERS
        path = f"aggregati/territori/{slug}.json"
        payload = await self._get_json(path, params=params or None)
        payload["source_url"] = self.source_url(path, params or None)
        payload["licenza"] = LICENZA_API
        return payload

    # ─────────────────────────── funding capacity ───────────────────────────

    async def funding_capacity(
        self,
        cod_comune: str | int | None = None,
        tema: str | None = None,
        ciclo: str | None = None,
        *,
        territorio: str | None = None,
    ) -> FundingCapacity:
        """Historical spending capacity (spend ratio + completed/total projects).

        ONE request to /aggregati/territori/{slug}.json (which already breaks
        totals down by state and theme and accepts the cycle filter) — no
        project pagination needed. With ``tema`` the ratio comes from that
        theme's slice; the per-state breakdown only exists territory-wide.
        """
        slug = await self._territorio_slug(territorio, cod_comune, None, None)
        if not slug:
            raise ValueError("Serve un territorio: cod_comune ISTAT oppure slug.")
        tema_slug = normalize_slug_value(tema, TEMI, "Tema") if tema else None
        ciclo_norm = normalize_ciclo(ciclo) if ciclo else None

        params = {"ciclo_programmazione": ciclo_norm} if ciclo_norm else None
        path = f"aggregati/territori/{slug}.json"
        payload = await self._get_json(path, params=params)

        contesto = payload.get("contesto") or {}
        agg = payload.get("aggregati") or {}
        stati_raw: dict[str, Any] = agg.get("stati_progetti") or {}

        def _totali(section: dict[str, Any]) -> dict[str, Any]:
            return section.get("totali") if isinstance(section.get("totali"), dict) else section

        if tema_slug:
            slice_ = agg.get("temi", {}).get(tema_slug)
            if slice_ is None:
                raise OpenCoesioneError(
                    f"Nessun dato per il tema {tema_slug!r} su {slug} "
                    f"(temi disponibili: {', '.join(sorted(agg.get('temi', {})))})."
                )
            tot = _totali(slice_)
        else:
            tot = _totali(agg.get("totali") or {})

        finanziato = parse_amount(tot.get("costo_pubblico"))
        pagamenti = parse_amount(tot.get("pagamenti"))
        progetti_totali = int(parse_amount(tot.get("progetti")) or 0) or None

        breakdown: list[StatoBreakdown] = []
        progetti_conclusi: int | None = None
        if not tema_slug:
            for stato in STATI:
                sezione = stati_raw.get(stato)
                if not sezione:
                    continue
                st = _totali(sezione)
                breakdown.append(
                    StatoBreakdown(
                        stato=stato,
                        progetti=int(parse_amount(st.get("progetti")) or 0),
                        costo_pubblico=parse_amount(st.get("costo_pubblico")),
                        pagamenti=parse_amount(st.get("pagamenti")),
                    )
                )
            progetti_conclusi = sum(b.progetti for b in breakdown if b.stato in STATI_CONCLUSI)

        spend_ratio = (
            round(pagamenti / finanziato, 4) if pagamenti is not None and finanziato else None
        )
        conclusi_ratio = (
            round(progetti_conclusi / progetti_totali, 4)
            if progetti_conclusi is not None and progetti_totali
            else None
        )
        return FundingCapacity(
            territorio=contesto.get("nome_territorio") or slug,
            slug=slug,
            popolazione=contesto.get("popolazione"),
            ciclo=ciclo_norm,
            tema=tema_slug,
            finanziato_totale=finanziato,
            pagamenti_totali=pagamenti,
            spend_ratio=spend_ratio,
            progetti_totali=progetti_totali,
            progetti_conclusi=progetti_conclusi,
            conclusi_ratio=conclusi_ratio,
            breakdown_stati=breakdown,
            data_aggiornamento=payload.get("data_aggiornamento"),
            source_url=self.source_url(path, params),
        )

    # ────────────────────────────── cache mgmt ──────────────────────────────

    @classmethod
    def cache_stats(cls) -> dict[str, Any]:
        c = cls._cache
        return {"size": len(c), "maxsize": c.maxsize, "ttl_seconds": c.ttl}

    @classmethod
    def cache_clear(cls) -> None:
        cls._cache.clear()
