"""Client per Centri d'Italia (openpolis): mirror locale dei CSV bulk + query.

Centri d'Italia NON è un'API REST: sono file CSV bulk su S3 (centri CAS/CPA/
hotspot, progetti e strutture SAI). Sono troppo pesanti (~11 MB + ~8.5 MB) per
un fetch a ogni chiamata tool → il **mirror locale è il meccanismo primario**:
al primo uso i CSV sono scaricati e caricati in uno SQLite read-only, poi
interrogati; il mirror è ricostruito quando la versione dataset cambia o supera
il TTL di refresh (i file sono versionati per anno, es. ``_v2026``).

Pattern ispirato alla parte ``opencoesione_query_local`` di opencoesione-mcp,
ma qui il mirror è la fonte primaria, non un supplemento a un'API live.

SQL sempre con parametri bound, mai SQL libero. Ogni output porta ``licenza``
(CC-BY 4.0), ``source_url`` (il CSV originale) e ``refreshed_at``. Fail-safe.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import os
import sqlite3
import tempfile
import time
from typing import Any

import httpx

from .mapping import (
    DATASETS,
    LICENZA,
    VERSION,
    norm_istat,
    parse_float,
    parse_int,
    source_url,
)

log = logging.getLogger("opendata-core.centriditalia")

DEFAULT_TIMEOUT = float(os.getenv("CENTRIDITALIA_HTTP_TIMEOUT", "120"))
#: TTL del mirror: oltre questo (o a versione cambiata) si ricostruisce.
REFRESH_TTL = int(os.getenv("CENTRIDITALIA_REFRESH_TTL_SECONDS", str(7 * 24 * 3600)))
USER_AGENT = os.getenv(
    "CENTRIDITALIA_USER_AGENT",
    "centriditalia-mcp-server/0.1 (+https://github.com/agent-engineering-studio)",
)
_MAX_RESULTS = 50

_INT_COLS = {"capienza", "presenze", "presenze_giornaliere"}
_REAL_COLS = {"costo_giornaliero_per_ospite"}


class CentriDItaliaError(RuntimeError):
    """Errore del connettore Centri d'Italia."""


def _default_db_path() -> str:
    return os.getenv(
        "CENTRIDITALIA_DB_PATH",
        os.path.join(tempfile.gettempdir(), "centriditalia_mirror.sqlite"),
    )


def _coerce(col: str, value: str) -> Any:
    v = (value or "").strip()
    if col in _INT_COLS:
        return parse_int(v)
    if col in _REAL_COLS:
        return parse_float(v)
    return v or None


def _load_csv_into(conn: sqlite3.Connection, dataset: str, text_stream: io.TextIOBase) -> int:
    """(Ri)crea la tabella del dataset e vi carica le colonne whitelisted. Ritorna righe."""
    spec = DATASETS[dataset]
    table, columns = spec["table"], spec["columns"]
    cols = list(columns)
    conn.execute(f"DROP TABLE IF EXISTS {table}")
    coldefs = ", ".join(f'"{c}" {t}' for c, t in columns.items())
    conn.execute(f"CREATE TABLE {table} ({coldefs})")
    reader = csv.DictReader(text_stream)
    placeholders = ", ".join("?" for _ in cols)
    col_list = ", ".join('"' + c + '"' for c in cols)
    insert = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
    batch: list[tuple] = []
    n = 0
    for row in reader:
        batch.append(tuple(_coerce(c, row.get(c, "")) for c in cols))
        if len(batch) >= 5000:
            conn.executemany(insert, batch)
            n += len(batch)
            batch = []
    if batch:
        conn.executemany(insert, batch)
        n += len(batch)
    # indici territoriali (le query filtrano sempre per codice ISTAT)
    for geo in ("comune_codice_istat", "provincia_cm_codice_istat", "regione_codice_istat"):
        if geo in columns:
            conn.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_{geo} ON {table}({geo})")
    if "centro_id" in columns:
        conn.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_centro ON {table}(centro_id)")
    return n


class CentriDItaliaClient:
    """Mirror locale + query sui dati Centri d'Italia. Usare come async ctx-mgr.

        async with CentriDItaliaClient() as c:
            await c.ensure_ready()
            out = await c.search_centri(comune_codice_istat="066049")
    """

    _build_lock = asyncio.Lock()

    def __init__(self, db_path: str | None = None, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._db_path = db_path or _default_db_path()
        self._timeout = timeout
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "CentriDItaliaClient":
        self._http = httpx.AsyncClient(
            timeout=self._timeout, follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    # ────────────────────────────── mirror build ───────────────────────────

    def _meta(self) -> dict[str, Any]:
        if not os.path.exists(self._db_path):
            return {}
        try:
            conn = sqlite3.connect(self._db_path)
            try:
                cur = conn.execute("SELECT key, value FROM _meta")
                return dict(cur.fetchall())
            finally:
                conn.close()
        except sqlite3.Error:
            return {}

    def _is_stale(self) -> bool:
        meta = self._meta()
        if not meta or meta.get("version") != VERSION:
            return True
        try:
            return (time.time() - float(meta.get("refreshed_at", 0))) > REFRESH_TTL
        except (TypeError, ValueError):
            return True

    async def ensure_ready(self, *, force: bool = False) -> dict[str, Any]:
        """Garantisce un mirror aggiornato; lo (ri)costruisce se serve. Ritorna refresh_info."""
        if not force and not self._is_stale():
            return self.refresh_info()
        async with self._build_lock:
            if not force and not self._is_stale():  # ricontrollo dopo il lock
                return self.refresh_info()
            sources: dict[str, str] = {}
            for name, spec in DATASETS.items():
                sources[name] = await self._download(spec["url"])
            try:
                await asyncio.to_thread(self._build, sources)
            finally:
                for path in sources.values():
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
        return self.refresh_info()

    async def _download(self, url: str) -> str:
        """Scarica un CSV in streaming su un file temporaneo; ritorna il path."""
        if self._http is None:
            raise RuntimeError("CentriDItaliaClient must be used as an async context manager")
        fd, path = tempfile.mkstemp(suffix=".csv", prefix="centriditalia_")
        try:
            with os.fdopen(fd, "wb") as fh:
                async with self._http.stream("GET", url) as resp:
                    if resp.status_code >= 400:
                        raise CentriDItaliaError(f"HTTP {resp.status_code} scaricando {url}")
                    async for chunk in resp.aiter_bytes():
                        fh.write(chunk)
        except httpx.HTTPError as exc:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise CentriDItaliaError(f"Errore di rete scaricando {url}: {exc}") from exc
        return path

    def _build(self, sources: dict[str, str]) -> None:
        """(Sync, in thread) ricostruisce il mirror SQLite dai CSV scaricati."""
        tmp = self._db_path + ".building"
        conn = sqlite3.connect(tmp)
        try:
            counts: dict[str, int] = {}
            for name, path in sources.items():
                with open(path, encoding="utf-8-sig", newline="") as fh:
                    counts[name] = _load_csv_into(conn, name, fh)
            conn.execute("CREATE TABLE _meta (key TEXT PRIMARY KEY, value TEXT)")
            conn.executemany(
                "INSERT INTO _meta (key, value) VALUES (?, ?)",
                [("version", VERSION), ("refreshed_at", str(time.time())),
                 *[(f"rows_{k}", str(v)) for k, v in counts.items()]],
            )
            conn.commit()
        finally:
            conn.close()
        os.replace(tmp, self._db_path)  # atomico: nessun mirror mezzo-costruito
        log.info("Centri d'Italia mirror ricostruito (%s): %s", VERSION, counts)

    def refresh_info(self) -> dict[str, Any]:
        meta = self._meta()
        return {
            "version": meta.get("version"),
            "refreshed_at": meta.get("refreshed_at"),
            "rows": {k[5:]: int(v) for k, v in meta.items() if k.startswith("rows_")},
            "licenza": LICENZA,
        }

    # ────────────────────────────── query core ─────────────────────────────

    def _query(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """(Sync, in thread) esegue una SELECT read-only e ritorna liste di dict."""
        if not os.path.exists(self._db_path):
            raise CentriDItaliaError("Mirror non pronto: chiama ensure_ready() prima.")
        conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def _geo_filter(comune: str | None, provincia: str | None, regione: str | None
                    ) -> tuple[str, dict[str, Any]]:
        if comune:
            return " AND comune_codice_istat = :geo ", {"geo": norm_istat(comune, 6)}
        if provincia:
            return " AND provincia_cm_codice_istat = :geo ", {"geo": norm_istat(provincia, 3)}
        if regione:
            return " AND regione_codice_istat = :geo ", {"geo": norm_istat(regione, 2)}
        return "", {}

    def _envelope(self, results: list[dict[str, Any]], dataset: str,
                  extra: dict[str, Any] | None = None) -> dict[str, Any]:
        out = {
            "results": results,
            "count": len(results),
            "source_url": source_url(dataset),
            "licenza": LICENZA,
            "refreshed_at": self._meta().get("refreshed_at"),
        }
        if extra:
            out.update(extra)
        return out

    # ────────────────────────────── tools ──────────────────────────────────

    async def search_centri(
        self, *,
        comune_codice_istat: str | None = None,
        provincia_cm_codice_istat: str | None = None,
        regione_codice_istat: str | None = None,
        tipologia_centro: str | None = None,
        tipologia_ospiti: str | None = None,
        operativita: str | None = None,
        rilevazione_da: str | None = None,
        rilevazione_a: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Centri CAS/CPA/hotspot filtrabili per territorio/tipologia/operatività/periodo."""
        await self.ensure_ready()
        limit = max(1, min(int(limit), _MAX_RESULTS))
        offset = max(0, int(offset))
        where, params = self._geo_filter(
            comune_codice_istat, provincia_cm_codice_istat, regione_codice_istat)
        for col, val in (("tipologia_centro", tipologia_centro),
                         ("tipologia_ospiti", tipologia_ospiti),
                         ("operativita", operativita)):
            if val:
                where += f" AND UPPER({col}) = UPPER(:{col}) "
                params[col] = val.strip()
        if rilevazione_da:
            where += " AND rilevazione_data >= :rda "
            params["rda"] = rilevazione_da.strip()
        if rilevazione_a:
            where += " AND rilevazione_data <= :ra "
            params["ra"] = rilevazione_a.strip()
        params.update(lim=limit, off=offset)
        sql = ("SELECT * FROM centri WHERE 1=1" + where
               + " ORDER BY rilevazione_data DESC, centro_id LIMIT :lim OFFSET :off")
        rows = await asyncio.to_thread(self._query, sql, params)
        return self._envelope(rows, "centri", {"has_more": len(rows) == limit,
                                               "next_offset": offset + limit})

    async def get_centro(self, centro_id: str | int) -> dict[str, Any]:
        """Serie storica di un centro: capienza/presenze/costo nel tempo, ente, convenzioni."""
        await self.ensure_ready()
        cid = str(centro_id).strip()
        rows = await asyncio.to_thread(
            self._query,
            "SELECT * FROM centri WHERE centro_id = :cid ORDER BY rilevazione_data",
            {"cid": cid},
        )
        return self._envelope(rows, "centri", {"centro_id": cid})

    async def territorio_aggregate(
        self, *,
        comune_codice_istat: str | None = None,
        provincia_cm_codice_istat: str | None = None,
        regione_codice_istat: str | None = None,
    ) -> dict[str, Any]:
        """Totali capienza/presenze/costo medio dei centri di un territorio.

        Usa la rilevazione PIÙ RECENTE per centro (il dataset è una serie storica),
        così i totali non sommano la storia dello stesso centro.
        """
        await self.ensure_ready()
        where, params = self._geo_filter(
            comune_codice_istat, provincia_cm_codice_istat, regione_codice_istat)
        if not where:
            raise ValueError("Serve un codice ISTAT (comune/provincia/regione).")
        # ultima rilevazione per centro nel territorio
        sql = (
            "WITH latest AS ("
            "  SELECT c.* FROM centri c "
            "  JOIN (SELECT centro_id, MAX(rilevazione_data) md FROM centri "
            "        WHERE 1=1" + where + " GROUP BY centro_id) m "
            "  ON c.centro_id = m.centro_id AND c.rilevazione_data = m.md"
            "  WHERE 1=1" + where + ") "
            "SELECT COUNT(DISTINCT centro_id) AS centri, "
            "       SUM(capienza) AS capienza_totale, "
            "       SUM(presenze_giornaliere) AS presenze_totali, "
            "       AVG(costo_giornaliero_per_ospite) AS costo_medio_giornaliero "
            "FROM latest"
        )
        rows = await asyncio.to_thread(self._query, sql, params)
        agg = rows[0] if rows else {}
        if agg.get("costo_medio_giornaliero") is not None:
            agg["costo_medio_giornaliero"] = round(agg["costo_medio_giornaliero"], 2)
        return self._envelope([], "centri", {"aggregato": agg})

    async def search_sai(
        self, *,
        kind: str = "progetti",
        comune_codice_istat: str | None = None,
        provincia_cm_codice_istat: str | None = None,
        regione_codice_istat: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Progetti o strutture SAI filtrabili per territorio (kind='progetti'|'strutture')."""
        await self.ensure_ready()
        dataset = "sai_progetti" if kind == "progetti" else "sai_strutture"
        if kind not in ("progetti", "strutture"):
            raise ValueError("kind deve essere 'progetti' o 'strutture'")
        limit = max(1, min(int(limit), _MAX_RESULTS))
        offset = max(0, int(offset))
        where, params = self._geo_filter(
            comune_codice_istat, provincia_cm_codice_istat, regione_codice_istat)
        params.update(lim=limit, off=offset)
        table = DATASETS[dataset]["table"]
        rows = await asyncio.to_thread(
            self._query,
            f"SELECT * FROM {table} WHERE 1=1{where} LIMIT :lim OFFSET :off",
            params,
        )
        return self._envelope(rows, dataset, {"kind": kind, "has_more": len(rows) == limit,
                                              "next_offset": offset + limit})

    async def reference_values(self) -> dict[str, Any]:
        """Valori distinti di tipologia_centro/tipologia_ospiti/operativita/procedura."""
        await self.ensure_ready()

        def _distinct(col: str) -> list[str]:
            rows = self._query(
                f"SELECT DISTINCT {col} AS v FROM centri WHERE {col} IS NOT NULL ORDER BY {col}",
                {},
            )
            return [r["v"] for r in rows if r["v"]]

        out = await asyncio.to_thread(
            lambda: {
                "tipologia_centro": _distinct("tipologia_centro"),
                "tipologia_ospiti": _distinct("tipologia_ospiti"),
                "operativita": _distinct("operativita"),
                "procedura_affidamento": _distinct("procedura_affidamento"),
            }
        )
        out["licenza"] = LICENZA
        out["refreshed_at"] = self._meta().get("refreshed_at")
        return out
