"""Async client per la REST del Knowledge Graph (ingest/delete documenti).

Il KG (repo knowledge-graph, FastAPI) espone:
  - POST /ingest      {file_path, thread_id, skip_existing} → {document_id, ...}
  - DELETE /documents/{document_id}

`file_path` è un path sul VOLUME CONDIVISO backend↔KG: il backend ci salva il
PDF e passa il path; il KG legge lo stesso volume. L'ingest è sincrono e può
durare (chunking + embedding + entity extraction), quindi il timeout è ampio.
"""

from __future__ import annotations

from typing import Any

import httpx


class KgError(Exception):
    """Errore di comunicazione/elaborazione col Knowledge Graph."""


class KgClient:
    def __init__(self, base_url: str, *, timeout: float = 300.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "KgClient":
        self._client = httpx.AsyncClient(
            base_url=self._base,
            timeout=self._timeout,
            headers={"Accept": "application/json"},
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _require(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("KgClient va usato come async context manager")
        return self._client

    async def ingest(
        self, file_path: str, thread_id: str, *, skip_existing: bool = True
    ) -> dict[str, Any]:
        """Ingestiona un documento sotto il namespace `thread_id`.

        Ritorna il payload del KG (document_id, chunks_processed, …). Solleva
        KgError su risposta non 2xx o errore di rete.
        """
        client = self._require()
        try:
            resp = await client.post(
                "/ingest",
                json={
                    "file_path": file_path,
                    "thread_id": thread_id,
                    "skip_existing": skip_existing,
                },
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:300] if exc.response is not None else ""
            raise KgError(f"ingest fallito ({exc.response.status_code}): {body}") from exc
        except httpx.HTTPError as exc:
            raise KgError(f"ingest non raggiungibile: {exc}") from exc

    async def delete_document(self, document_id: str) -> None:
        """Elimina un documento (e i suoi chunk) dal KG. Idempotente lato KG."""
        client = self._require()
        try:
            resp = await client.delete(f"/documents/{document_id}")
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return  # già assente: nulla da fare
            raise KgError(f"delete fallito: {exc}") from exc
        except httpx.HTTPError as exc:
            raise KgError(f"delete non raggiungibile: {exc}") from exc
