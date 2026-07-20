"""Async HTTP client for the OpenPNRR API (openpolis — Italian NRRP open data).

API root: ``https://openpnrr.it/api/v1`` (plain JSON, DRF pagination
``{count, next, previous, results}``; **no authentication** on the list
resources). Behaviours verified during discovery:

  - **NEVER a trailing slash** on endpoints: ``/progetti`` works, ``/progetti/``
    returns a 404 HTML page. The client always builds slash-free paths.
  - list resources are paginated with ``page`` / ``page_size`` (capped here at
    ``MAX_PAGE_SIZE`` to protect the LLM context budget);
  - ``/territori?istat_id=072021`` maps directly onto the ISTAT codes used
    across the platform → resolve ISTAT → OpenPNRR territory id, then filter
    ``/progetti?territori={id}`` (the ``/territori/{id}/progetti`` endpoint
    returns an aggregate summary object, not a project list);
  - ``progetti`` is huge (~280k records) → always filter server-side, never scan;
  - amounts arrive as decimal strings (``"3773260.36"``) → ``parse_amount``;
  - project list rows carry no ``id`` field but a resolvable ``url`` whose last
    segment is the numeric id used by ``/progetti/{id}``.

Licence of API data: **ODbL 1.0** — every public method returns a resolvable
``source_url`` and the ``licenza`` string so callers can attribute openpolis.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx
from cachetools import TTLCache

from .mapping import (
    LICENZA,
    MAX_PAGE_SIZE,
    MISURE_FILTERS,
    PROGETTI_FILTERS,
    SCADENZE_FILTERS,
    TERRITORI_FILTERS,
    id_from_url,
    parse_amount,
)
from .models import Misura, ProgettoSummary, Scadenza, Territorio

DEFAULT_TIMEOUT = float(os.getenv("OPENPNRR_HTTP_TIMEOUT", "60"))
#: Root senza trailing slash — vedi docstring del modulo (con slash → 404 HTML).
DEFAULT_BASE_URL = os.getenv("OPENPNRR_BASE_URL", "https://openpnrr.it/api/v1")
USER_AGENT = os.getenv(
    "OPENPNRR_USER_AGENT",
    "openpnrr-mcp-server/0.1 (+https://github.com/agent-engineering-studio)",
)
CACHE_TTL = int(os.getenv("OPENPNRR_CACHE_TTL_SECONDS", "3600"))
CACHE_MAXSIZE = int(os.getenv("OPENPNRR_CACHE_MAXSIZE", "512"))
MAX_RETRIES = 4

log = logging.getLogger("opendata-core.openpnrr")


class OpenPnrrError(RuntimeError):
    """Raised when the OpenPNRR endpoint returns an unexpected payload or HTTP error."""


def _normalize_base(base_url: str | None) -> str:
    base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    return base


class OpenPnrrClient:
    """Thin async wrapper around the OpenPNRR JSON API.

    Usage:
        async with OpenPnrrClient() as c:
            t = await c.resolve_territorio(istat_id="072021")
            projects = await c.search_progetti(territori=t.id)
    """

    # Condivisa tra istanze: lookup territori e reference sono stabili → le
    # chiamate successive nello stesso processo ne beneficiano.
    _cache: TTLCache = TTLCache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)

    def __init__(self, timeout: float = DEFAULT_TIMEOUT, base_url: str | None = None) -> None:
        self._timeout = timeout
        self._base = _normalize_base(base_url)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "OpenPnrrClient":
        self._client = httpx.AsyncClient(
            base_url=self._base,
            timeout=self._timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ────────────────────────────── core HTTP ──────────────────────────────

    def source_url(self, path: str, params: dict[str, Any] | None = None) -> str:
        """URL risolvibile di una richiesta — per il blocco `sources` di ogni output."""
        url = httpx.URL(self._base + "/" + path.strip("/"))
        if params:
            url = url.copy_merge_params({k: v for k, v in sorted(params.items()) if v is not None})
        return str(url)

    async def _get_json(
        self, path: str, *, params: dict[str, Any] | None = None, cache: bool = True
    ) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("OpenPnrrClient must be used as an async context manager")
        # NB: mai trailing slash — vedi docstring del modulo.
        rel = "/" + path.strip("/")
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        key = (self._base, rel, tuple(sorted(clean.items())))
        if cache and key in self._cache:
            return self._cache[key]  # type: ignore[return-value]

        url = self.source_url(path, clean)
        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._client.get(rel, params=clean or None)
            except httpx.HTTPError as exc:
                log.error("OpenPNRR transport error GET %s: %s", url, exc)
                raise OpenPnrrError(f"Transport error on GET {path}: {exc}") from exc

            if resp.status_code == 429 or (resp.status_code >= 500 and attempt < MAX_RETRIES - 1):
                delay = 2.0**attempt
                log.warning("OpenPNRR HTTP %s on %s — retry in %.1fs", resp.status_code, url, delay)
                await asyncio.sleep(delay)
                continue
            if resp.status_code == 404:
                raise OpenPnrrError(
                    f"Not found: {url} — verifica l'id/codice (attenzione: niente slash finale)."
                )
            if resp.status_code >= 400:
                snippet = resp.text[:300].replace("\n", " ")
                raise OpenPnrrError(f"HTTP {resp.status_code} on GET {path}: {snippet}")

            try:
                payload = resp.json()
            except ValueError as exc:
                raise OpenPnrrError(f"Non-JSON response from {path}: {resp.text[:300]}") from exc
            if not isinstance(payload, dict):
                raise OpenPnrrError(f"Unexpected payload type from {path}: {type(payload).__name__}")
            if cache:
                self._cache[key] = payload
            return payload

        raise OpenPnrrError(f"OpenPNRR unavailable after {MAX_RETRIES} attempts on {url}")

    @staticmethod
    def _paged(limit: int, offset: int) -> tuple[int, int, int]:
        """(page, page_size, effective_limit) da limit/offset (pagine, non offset libero)."""
        limit = max(1, min(int(limit), MAX_PAGE_SIZE))
        offset = max(0, int(offset))
        if offset % limit:
            raise ValueError(
                f"offset ({offset}) deve essere un multiplo di limit ({limit}): "
                "l'API OpenPNRR pagina per pagine."
            )
        return offset // limit + 1, limit, limit

    def _envelope(self, payload: dict[str, Any], path: str, params: dict[str, Any],
                  offset: int, limit: int, results: list[Any]) -> dict[str, Any]:
        has_more = payload.get("next") is not None
        return {
            "total": int(payload.get("count") or 0),
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "results": results,
            "source_url": self.source_url(path, params),
            "licenza": LICENZA,
        }

    # ─────────────────────────── territory resolution ───────────────────────

    async def resolve_territorio(
        self,
        *,
        istat_id: str | None = None,
        opdm_id: str | int | None = None,
        nome: str | None = None,
        tipologia: str | None = None,
    ) -> Territorio | None:
        """Risolve un codice ISTAT (o un nome/opdm_id) al record /territori con il suo id.

        ``territori.istat_id`` è il codice ISTAT usato nel resto della piattaforma.
        Ritorna None quando nulla corrisponde.
        """
        params: dict[str, Any] = {}
        if istat_id:
            params["istat_id"] = str(istat_id).strip()
        elif opdm_id is not None:
            params["opdm_id"] = opdm_id
        elif nome:
            params["denominazione"] = nome.strip()
        else:
            raise ValueError("Serve almeno uno tra istat_id / opdm_id / nome.")
        if tipologia:
            params["tipologia"] = tipologia.strip().upper()
        assert set(params) <= TERRITORI_FILTERS

        payload = await self._get_json("territori", params=params)
        results = payload.get("results") or []
        if not results:
            return None
        if nome and len(results) > 1:
            exact = [r for r in results if str(r.get("denominazione", "")).lower() == nome.lower()]
            if exact:
                results = exact
        rec = results[0]
        return Territorio(**{k: rec.get(k) for k in Territorio.model_fields})

    async def _territorio_id(self, territori: int | str | None, istat_id: str | None) -> int | None:
        """id territorio da un id esplicito o da un codice ISTAT; None se non dato."""
        if territori is not None:
            return int(territori)
        if not istat_id:
            return None
        t = await self.resolve_territorio(istat_id=istat_id)
        if t is None:
            raise OpenPnrrError(
                f"Nessun territorio OpenPNRR per il codice ISTAT {istat_id!r}."
            )
        return t.id

    # ────────────────────────────── projects ────────────────────────────────

    @staticmethod
    def _slim_project(rec: dict[str, Any]) -> ProgettoSummary:
        return ProgettoSummary(
            id=rec.get("id") or id_from_url(rec.get("url")),
            codice_locale_progetto=rec.get("codice_locale_progetto") or None,
            titolo=rec.get("titolo") or None,
            cup=rec.get("cup") or None,
            misura=str(rec["misura"]) if rec.get("misura") is not None else None,
            soggetto_attuatore=(
                str(rec["soggetto_attuatore"]) if rec.get("soggetto_attuatore") is not None else None
            ),
            stato_avanzamento=rec.get("stato_avanzamento") or None,
            is_validato=rec.get("is_validato"),
            finanziamento_totale=parse_amount(rec.get("finanziamento_totale")),
            finanziamento_pnrr=parse_amount(rec.get("finanziamento_pnrr")),
            territori=rec.get("territori") or [],
            url=rec.get("url") or None,
        )

    async def search_progetti(
        self,
        *,
        territori: int | str | None = None,
        istat_id: str | None = None,
        descrizione: str | None = None,
        misura_codice_identificativo: str | None = None,
        componente_codice_identificativo: str | None = None,
        missione_codice_identificativo: str | None = None,
        organizzazioni: str | int | None = None,
        tema: str | int | None = None,
        validato: bool | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Cerca /progetti coi filtri verificati; scope territoriale via id o codice ISTAT.

        Ritorna ``{total, has_more, next_offset, results, source_url, licenza}``
        con dict ``ProgettoSummary`` snelli in ``results``.
        """
        page, page_size, limit = self._paged(limit, offset)
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        tid = await self._territorio_id(territori, istat_id)
        if tid is not None:
            params["territori"] = tid
        if descrizione:
            params["descrizione"] = descrizione.strip()
        if misura_codice_identificativo:
            params["misura_codice_identificativo"] = misura_codice_identificativo.strip()
        if componente_codice_identificativo:
            params["componente__codice_identificativo"] = componente_codice_identificativo.strip()
        if missione_codice_identificativo:
            params["missione__codice_identificativo"] = missione_codice_identificativo.strip()
        if organizzazioni is not None:
            params["organizzazioni"] = organizzazioni
        if tema is not None:
            params["tema"] = tema
        if validato is not None:
            params["validato"] = str(bool(validato)).lower()
        assert set(params) <= PROGETTI_FILTERS | {"page", "page_size"}

        payload = await self._get_json("progetti", params=params)
        results = [self._slim_project(r).model_dump() for r in payload.get("results") or []]
        return self._envelope(payload, "progetti", params, offset, limit, results)

    async def get_progetto(self, progetto_id: int | str) -> dict[str, Any]:
        """Record di dettaglio completo di un progetto per id numerico.

        Aggiunge ``pagamenti_totale`` (somma dei ``pagamento_tot`` della lista
        pagamenti) come comodità, mantenendo i campi grezzi.
        """
        pid = str(progetto_id).strip()
        if not pid.isdigit():
            raise ValueError(f"id progetto non numerico: {progetto_id!r}")
        path = f"progetti/{pid}"
        payload = await self._get_json(path)
        pagamenti = payload.get("pagamenti") or []
        if isinstance(pagamenti, list) and pagamenti:
            tot = sum(parse_amount(p.get("pagamento_tot")) or 0.0 for p in pagamenti)
            payload["pagamenti_totale"] = round(tot, 2)
        payload["source_url"] = self.source_url(path)
        payload["licenza"] = LICENZA
        return payload

    # ────────────────────────────── misure ──────────────────────────────────

    async def search_misure(
        self,
        *,
        codice_misura: str | None = None,
        componente_codice: str | None = None,
        tipologia: str | None = None,
        tipo_riforma: str | None = None,
        tipo_investimento: str | None = None,
        status: str | None = None,
        territori: int | str | None = None,
        istat_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Cerca le misure PNRR (/misure) coi filtri verificati."""
        page, page_size, limit = self._paged(limit, offset)
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if codice_misura:
            params["codice_misura"] = codice_misura.strip()
        if componente_codice:
            params["componente__codice"] = componente_codice.strip()
        if tipologia:
            params["tipologia"] = tipologia.strip()
        if tipo_riforma:
            params["tipo_riforma"] = tipo_riforma.strip()
        if tipo_investimento:
            params["tipo_investimento"] = tipo_investimento.strip()
        if status:
            params["status"] = status.strip()
        tid = await self._territorio_id(territori, istat_id)
        if tid is not None:
            params["territori"] = tid
        assert set(params) <= MISURE_FILTERS | {"page", "page_size"}

        payload = await self._get_json("misure", params=params)
        results = [
            Misura(**{k: r.get(k) for k in Misura.model_fields}).model_dump()
            for r in payload.get("results") or []
        ]
        return self._envelope(payload, "misure", params, offset, limit, results)

    # ────────────────────────────── scadenze ────────────────────────────────

    async def search_scadenze(
        self,
        *,
        misure_codice_identificativo: str | None = None,
        status: str | None = None,
        tempistica_completamento_anno: int | None = None,
        tempistica_completamento_trimestre: str | None = None,
        ita_ue: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Cerca le scadenze/milestone PNRR (/scadenze) coi filtri verificati."""
        page, page_size, limit = self._paged(limit, offset)
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if misure_codice_identificativo:
            params["misure__codice_identificativo"] = misure_codice_identificativo.strip()
        if status:
            params["status"] = status.strip()
        if tempistica_completamento_anno is not None:
            params["tempistica_completamento_anno"] = int(tempistica_completamento_anno)
        if tempistica_completamento_trimestre:
            params["tempistica_completamento_trimestre"] = str(tempistica_completamento_trimestre).strip()
        if ita_ue:
            params["ita_ue"] = ita_ue.strip().upper()
        assert set(params) <= SCADENZE_FILTERS | {"page", "page_size"}

        payload = await self._get_json("scadenze", params=params)
        results = [
            Scadenza(**{k: r.get(k) for k in Scadenza.model_fields}).model_dump()
            for r in payload.get("results") or []
        ]
        return self._envelope(payload, "scadenze", params, offset, limit, results)

    # ─────────────────────────── reference structure ────────────────────────

    async def reference_struttura(self) -> dict[str, Any]:
        """Struttura statica PNRR: missioni, componenti, temi, priorità (reference).

        Utile per risolvere i codici usati come filtri di /progetti e /misure.
        Ogni risorsa è piccola (6-7 missioni, 17 componenti, ~45 temi, 15 priorità).
        """
        out: dict[str, Any] = {"licenza": LICENZA, "sources": []}
        for risorsa in ("missioni", "componenti", "temi", "priorita"):
            payload = await self._get_json(risorsa, params={"page_size": MAX_PAGE_SIZE})
            out[risorsa] = payload.get("results") or []
            out["sources"].append(self.source_url(risorsa))
        return out

    # ────────────────────────────── cache mgmt ──────────────────────────────

    @classmethod
    def cache_clear(cls) -> None:
        cls._cache.clear()
